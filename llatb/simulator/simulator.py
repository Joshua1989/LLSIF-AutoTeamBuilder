import numpy as np
import pandas as pd

import json, urllib.request, llatb
from llatb.common.global_var import *
from llatb.simulator.skill_tracker import SkillTracker
from llatb.common.config import live_archive_dir, misc_path, icon_path
from llatb.framework import Live
from IPython.display import HTML


class Simulator:
	def __init__(self, team, guest_cskill=None, boosts={}):
		self.card_list = team.card_list
		# Compute team total attribute when judge skill is not active and active
		res = team.team_strength(guest_cskill)
		temp = np.array(res['displayed_card_attr'])
		total = np.zeros((2,3))
		for i,card in enumerate(self.card_list):
			total += temp[i,:]
			for gem in card.equipped_gems:
				if gem.effect == 'judge_boost':
					attr_idx = attr_list.index(gem.attribute)
					total[1,attr_idx] += gem.value/100*temp[i,attr_idx]
		total += np.array(res['center_skill_bonus']) + np.array(res['center_SIS_bonus'])
		self.team_attr = total
		self.team_hp = np.array([card.hp for card in self.card_list]).sum()
		# Compute purchase boosts
		self.boosts = {'Perfect Support':0, 'Tap Score Up':0, 'Skill Up':0, 'Stamina Restore':0}
		self.boosts.update(boosts)
	def _load_live(self, name, difficulty):
		# Extract live info from file
		self.live = Live(name, difficulty)
		self.note_list = self.live.note_list.copy()
	def _init_simul(self, prob):
		# Assign random tap accuracy for each note
		df = self.note_list.copy()
		accr_list = np.array(['Perfect', 'Great', 'Good', 'Bad', 'Miss'])
		df.index = [str(i)+'h'*int(x) for i,x in enumerate(df.long,1)]
		# For all long note, split head and tail
		df_tail = df[df.long].copy()
		df_tail['timing_sec'] = df_tail.apply(lambda x: x['timing_sec']+x['effect_value'], axis=1)
		df_tail.index = [x[:-1]+'t' for x in list(df_tail.index)]
		df = pd.concat((df,df_tail), axis=0)
		df['index'] = df.index
		df = df.sort_values(by=['timing_sec','index'])
		df['accuracy'] = accr_list[np.random.choice(len(prob), len(df), p=prob)]
		# Construct initialized data frame
		df = df[['index', 'timing_sec', 'position', 'long', 'star', 'swing', 'accuracy', 'notes_level']]
		df['accuracy*'] = 'Miss'
		df['time_elapse'] = np.diff(np.concatenate(([0], df.timing_sec.values)))
		df = df.assign(cum_score=0, hp=0, combo=0, note=0, perfect=0, score=0, skill_active=False, 
					   remain_perfect_support=self.boosts['Perfect Support'],
					   judge_end_time=0, weak_judge_end_time=0, skill_score=0, hp_restore=0)
		for i in range(len(self.card_list)):
			df['card {0}'.format(i+1)] = np.NaN
		columns = ['index', 'long', 'star', 'swing', 'position', 'notes_level',
				   'timing_sec', 'time_elapse', 'judge_end_time', 'weak_judge_end_time',
				   'accuracy', 'accuracy*', 'hp', 'remain_perfect_support', 'note', 'combo', 
				   'perfect', 'cum_score', 'score', 'skill_score', 'hp_restore'] + ['card {0}'.format(i+1) for i in range(len(self.card_list))]
		df_data = [row.T.to_dict() for index, row in df.iterrows()]
		self.simul_traj = df_data
		self.columns = columns
		self.global_status = {'judge_end_time':0, 'weak_judge_end_time':0, 'note':0, 'combo':0, 
							  'hp':self.team_hp, 'cum_score':0, 'head_accuracy_dict':dict(),
							  'note_stat':{'Perfect':0, 'Great':0, 'Good':0, 'Bad':0, 'Miss':0}, 
							  'remain_perfect_support': self.boosts['Perfect Support']}
		# Initialize skill tracker
		self.skill_tracker = [SkillTracker(card, self.boosts['Skill Up']) for card in self.card_list]
	def _update_global_status(self, note):
		accuracy = note['accuracy']
		# First consider weak judge skill, then strong judge skill, finally perfect support
		if note['timing_sec'] < self.global_status['weak_judge_end_time'] and note['accuracy'] in ['Great']:
			accuracy = 'Perfect'
		elif note['timing_sec'] < self.global_status['judge_end_time'] and note['accuracy'] in ['Great', 'Good']:
			accuracy = 'Perfect'
		elif accuracy in ['Good', 'Bad'] and self.global_status['remain_perfect_support'] > 0:
			accuracy = 'Perfect'
			self.global_status['remain_perfect_support'] -= 1
		# Compute judge coefficient for different cases
		if note['index'][-1] not in ['h', 't']: # Normal note
			# Compute the judge coefficient and hp penalty
			judge_coeff = accuracy_factor[accuracy]
		elif note['index'][-1] == 'h': # Head of long notes
			# Compute the judge coefficient, set it to zero since score are compute after the long note ends
			judge_coeff = 0
			# Store the head accuracy for dealing with its tail
			self.global_status['head_accuracy_dict'][note['index']] = accuracy
		elif note['index'][-1] == 't': # Tail of long notes
			# If the note is the tail of a long note, check if the judge result for head
			head_accuracy = self.global_status['head_accuracy_dict'][note['index'].replace('t','h')]
			# If the head is Bad or Miss, there is no chance to reach the tail
			# just set to Miss, and there is no hp penalty since the head is already penalized
			if head_accuracy in ['Bad', 'Miss']: accuracy = 'Miss'
			judge_coeff = accuracy_factor[head_accuracy] * accuracy_factor[accuracy]
			# For long note, the final accuracy is the worse one between head and tail
			accuracy = accuracy_list[max(accuracy_list.index(head_accuracy), accuracy_list.index(accuracy))]
		# Update all note counter
		self.global_status['note'] = self.global_status['note'] if accuracy == 'Miss' or note['index'][-1] == 'h' else self.global_status['note']+1
		self.global_status['combo'] = 0 if accuracy not in ['Perfect', 'Great'] else self.global_status['combo']+(note['index'][-1] != 'h')
		self.global_status['note_stat'][accuracy] += (note['index'][-1] != 'h')
		self.global_status['hp'] -= hp_penalty_dict[note['star']][accuracy]
		return accuracy, judge_coeff
	def _compute_tap_score(self, note, group_coeff, attr_coeff, judge_coeff):
		# Compute team total attribute, if judge skill is active and 
		# there are memebers equipped with timing boosting gems, then this value will change
		judge_active = int(note['timing_sec'] < self.global_status['judge_end_time'])
		attr_idx = attr_list.index(self.live.attr)
		team_value = base_score_factor * self.team_attr[judge_active, attr_idx]

		# Compute base card scoring
		combo_coeff = combo_factor(self.global_status['combo'])
		type_coeff = (1+(long_factor-1)*note['long']) * (1+(swing_factor-1)*note['swing'])
		pos = 9 - note['position'] # Position in note are ordered clockwise
		score = team_value * type_coeff * judge_coeff * combo_coeff * attr_coeff[pos] * group_coeff[pos]
		# print(team_value, type_coeff, judge_coeff, combo_coeff, attr_coeff[pos], group_coeff[pos])
		score = int( score * (1+self.boosts['Tap Score Up']) )
		self.skill_tracker[pos].cum_base_score += score
		return score
	def _add_skill_reward(self, note, reward):
		self.global_status['cum_score'] += reward['score']
		self.global_status['hp'] = np.minimum(self.team_hp, self.global_status['hp']+reward['hp'])
		self.global_status['judge_end_time'] = self.global_status['judge_end_time'] if reward['judge'] == 0 else np.maximum(self.global_status['judge_end_time'], note['timing_sec']+reward['judge'])
		self.global_status['weak_judge_end_time'] = self.global_status['weak_judge_end_time'] if reward['weak_judge'] == 0 else np.maximum(self.global_status['weak_judge_end_time'], note['timing_sec']+reward['weak_judge'])
	def _gen_summary(self, col_width=50):
		pd.set_option('display.max_colwidth', -1)
		song_name = '<p style="color:{0};">{1}</p>'.format(attr_color[self.live.attr], self.live.name)
		df_head = pd.DataFrame({'Song Name': [song_name]})
		df_head['Difficulty'] = self.live.difficulty
		df_head['Score'] = int(self.global_status['cum_score'])
		df_head['Cover Rate'] = '{0:.2f}%'.format(100*(self.simul_result['timing_sec'] <= self.simul_result['judge_end_time']).mean())
		df_head['Max Combo'] = self.simul_result['combo'].max()
		for accr in accuracy_list:
			df_head[accr] = self.global_status['note_stat'][accr]
		card = ['<img src="{0}" width={1} />'.format(icon_path(card.card_id, card.idolized), col_width) for card in self.card_list]
		summary, keys = [], ['base_score', 'score', 'hp', 'judge', 'weak_judge']
		for i in range(len(card)):
			temp = {k:getattr(self.skill_tracker[i], 'cum_'+k) for k in keys}
			temp['card'] = card[i]
			summary.append(temp)
		df = pd.DataFrame(summary, columns=['card']+keys)
		df['score'] = df['score'].apply(lambda x: int(x))
		df = df.append(pd.DataFrame(df.sum()).transpose())
		df.index = ['L1', 'L2', 'L3', 'L4', 'C', 'R4', 'R3', 'R2', 'R1', 'Total']
		df.loc['Total', 'card'] = ''
		html_code = df_head.to_html(escape=False, index=False) + df.transpose().to_html(escape=False)
		return HTML(html_code)

	def simulate(self, name, difficulty, prob, save_to=None):
		self._load_live(name, difficulty)
		self._init_simul(prob)
		# Compute group bonus and attribute bonus
		group_coeff = [1+0.1*(card.main_attr==self.live.attr) for card in self.card_list]
		attr_coeff = [1+0.1*(self.live.group in card.tags) for card in self.card_list]
		
		for i, curr_note in enumerate(self.simul_traj):
			# Adjust judge if the judge effect is active, update judge coefficient and all note counter
			accuracy, judge_coeff = self._update_global_status(curr_note)
			# Update HP based on adjusted accuracy
			curr_note['accuracy*'] = accuracy
			curr_note['perfect'] = self.global_status['note_stat']['Perfect']
			curr_note['remain_perfect_support'] = self.global_status['remain_perfect_support']
			curr_note.update({x:self.global_status[x] for x in ['combo', 'note', 'hp'] })
			# Update card basic score
			score = self._compute_tap_score(curr_note, group_coeff, attr_coeff, judge_coeff)
			self.global_status['cum_score'] += int(score)
			curr_note['score'], curr_note['cum_score'] = int(score), self.global_status['cum_score']
			# Compute card skill 
			for card_idx, skill in enumerate(self.skill_tracker,1):
				reward = skill.update(curr_note, self.team_hp)
				self._add_skill_reward(curr_note, reward)
				curr_note['skill_score'] += reward['score']
				curr_note['hp_restore'] += reward['hp']
				curr_note['score'] += reward['score']
				curr_note['cum_score'] = self.global_status['cum_score']
				curr_note['hp'] = self.global_status['hp']
				curr_note['judge_end_time'] = self.global_status['judge_end_time']
				curr_note['weak_judge_end_time'] = self.global_status['weak_judge_end_time']
				skill_in_effect = np.array(list(reward.values())).sum() > 0 or skill.remain > 0
				if skill.effect_type in ['Weak Judge', 'Strong Judge']:
					curr_note['card {0}'.format(card_idx)] = skill_in_effect * skill.remain/skill.duration
				else:
					curr_note['card {0}'.format(card_idx)] = int(skill_in_effect)
		self.simul_result = pd.DataFrame(self.simul_traj, columns=self.columns)

		if save_to is not None:
			self.show_simul(filename=save_to)
		return self._gen_summary()

	def show_simul(self, col_width=30, ext_cols=[], filename='test.html'):
		def determine_note_type(df):
			df = df.assign(direction=0)
			cal_dir = lambda x: np.concatenate((np.diff(x),[np.diff(x)[-1]]))
			for i in range(2,df['notes_level'].max()+1):
				df.loc[df.notes_level==i,'direction'] = cal_dir(df[df.notes_level==i]['position'].values)
			attr = self.live.attr
			notes = {'note type '+str(l+1):[] for l in range(len(self.card_list))}
			swing_dir = df.direction.apply(lambda x: 'left' if x>0 else 'right')
			long_on = [False]*9
			for i, row in df.iterrows():
				pos = 9 - row.position
				for l in range(len(self.card_list)):
					key = 'note type '+str(l+1)
					if l == pos:
						# If it is not the head and tail of a long note
						if row['index'][-1] not in ['h', 't']:
							# Normal note or Star note
							if not row.swing:
								notes[key].append(attr + (' Star' if row.star else ' Note'))
							# Swing note
							elif row.swing:
								notes[key].append(attr + ' Swing ' + swing_dir[i])
						# If it is the head and tail of a long note
						else:
							long_on[l] = row['index'][-1] == 'h'
							notes[key].append(attr + ' Note')
					else:
						# If a long note is present
						notes[key].append('long' if long_on[l] else 'empty')
			return pd.DataFrame(notes)
		def format_row(row, max_hp, card_list):
			fmt = '<p style="color:{0};"> {1} </p>'
			res = dict()
			color = 'cyan' if row.swing else ('red' if row.star else ('blue' if row.long else 'black'))
			res['index'] = fmt.format(color, row['index'])
			color_fun = lambda n: 'rgb({0},{1},0)'.format(int((255*n/4)*0.8), int((255-255*n/4)*0.8))

			color = {'Perfect':color_fun(0), 'Great':color_fun(1), 'Good':color_fun(2), 'Bad':color_fun(3), 'Miss':color_fun(4)}
			res['accuracy'] = fmt.format(color[row.accuracy], row.accuracy)
			res['accuracy*'] = fmt.format(color[row['accuracy*']], row['accuracy*'])
			
			color_fun = lambda hp: 'rgb({0},{1},{0})'.format(int((255-255*hp/max_hp)*0.8), int((255*hp/max_hp)*0.8))
			res['hp'] = fmt.format(color_fun(row.hp), row.hp)
			
			res['cum_score'], res['score'] = row.cum_score, row.score
			res['time'] = row.timing_sec
			res['note'], res['combo'], res['perfect'] = row.note, row.combo, row.perfect

			res.update({ x:row[x] for x in ext_cols })
			
			for i, card in enumerate(card_list,1):
				note_type, content = row['note type '+str(i)], ''
				if 'Note' in note_type:
					content += '<img style="position: relative;" src="{0}" width={1} />'.format(misc_path(note_type), col_width)
				elif 'Star' in note_type:
				 	content += '<img style="position: relative;" src="{0}" width={1} />'.format(misc_path(note_type.replace('Star','Note')), col_width)
				 	content += '<img style="position: absolute; top: 0px; left: 0px;" src="{0}" width={1} />'.format(misc_path('star'), col_width)
				elif 'Swing' in note_type:
					if 'left' in note_type:
				 		content += '<img style="position: relative;transform: rotateZ(180deg)" src="{0}" width={1} />'.format(misc_path(note_type.replace(' left','')), col_width)
					elif 'right' in note_type:
				 		content += '<img style="position: relative;" src="{0}" width={1} />'.format(misc_path(note_type.replace(' right','')), col_width)
				if row['card '+str(i)] > 0:
					top, left = -0.3*col_width if content=='' else 0.15*col_width, 0.15*col_width
					content += '<img style="position: absolute; top: {0}px; left: {1}px;opacity:{4}" src="{2}" width={3} /></div>'''.format(top, left, misc_path(card.skill.effect_type), 0.7*col_width, row['card '+str(i)]*0.7+0.3)
				col = '<img src="{0}" width={1} />'.format(icon_path(card.card_id, card.idolized), col_width)
				res[col] = '<div style="position: relative;">{0}</div>'.format(content)
			return res

		columns = ['index', 'time', 'accuracy', 'accuracy*', 'hp', 'note', 'combo', 'perfect', 'cum_score', 'score']
		columns += ['<img src="{0}" width={1} />'.format(icon_path(card.card_id, card.idolized), col_width) for card in self.card_list]
		columns += ext_cols

		df = pd.concat((self.simul_result, determine_note_type(self.simul_result)), axis=1)
		data = [format_row(row, self.team_hp, self.card_list) for _, row in df.iterrows()]
		pd.set_option('display.max_colwidth', -1)
		df = pd.DataFrame(data, columns=columns).set_index('index')
		df.cum_score = df.cum_score.apply(lambda x:int(x))
		df.score = df.score.apply(lambda x:int(x))
		html_code = df.to_html(escape=False)
		with open(filename, 'w') as fp:
			fp.write(html_code)
		print('File saved to', filename)