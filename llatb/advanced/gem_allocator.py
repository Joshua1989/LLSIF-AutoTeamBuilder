from collections import defaultdict
import math, itertools, copy, json
from llatb.advanced.advanced_card import *
from llatb.framework import Team
from llatb.common.display import gem_slot_pic, view_cards
from llatb.common.config import card_archive_dir, misc_path, icon_path, gem_path, html_template
from IPython.display import HTML

class GemAllocator:
	def __init__(self, adv_card_list, live, setting, owned_gem):
		if type(adv_card_list) != list or len(adv_card_list) != 9:
			print('9 cards are required to build a team!')
			raise
		self.card_list = adv_card_list
		self.live = live
		self.setting = setting
		self.guest_cskill = self.setting.get('guest_cskill', None)
		self.owned_gem = owned_gem

	def update_gem_score(self, sort=False):
		# Compute Average Position Bonus
		mu = np.array([card.mu for card in self.card_list[1:]])
		zeta = self.live.combo_weight_fraction.copy()[[0,1,2,3,5,6,7,8]]
		mu.sort()
		zeta.sort()
		self.mu_bar = self.card_list[0].mu * self.live.combo_weight_fraction[4] + (mu*zeta).sum()
		# Compute team total cover rate
		if hasattr(self.live, 'note_list'):
			temp = np.ones(self.live.note_number)
			for card in self.card_list:
				temp *= 1 - card.CR_list
			self.team_CR = (1-temp).mean()
		else:
			self.team_CR = 1 - (1-np.array([card.CR for card in self.card_list])).prod()
		# Update settings to compute skill gain of Skill Up and Stamina Restore skills
		new_setting = self.setting.copy()
		new_setting['attr_group_factor'] = self.mu_bar
		new_setting['perfect_rate'] = 1 - (1-self.live.perfect_rate) * (1-self.team_CR)
		# Compute strength per tap after amending perfect rate
		for card in self.card_list:
			if card.skill is not None:
				self.strength_per_pt_tap = card.skill.skill_gain(setting=new_setting)[1]

		cskill_bonus = np.array([card.cskill_bonus for card in self.card_list])
		base_bond_value = np.array([card.base_bond_value for card in self.card_list])
		team_base_bond_cskill_value = (base_bond_value*(1+cskill_bonus)).sum()
		# Compute gem score for each card
		boost = self.live.pts_per_strength * self.mu_bar * self.setting['score_up_rate']
		team_base_score, best_gem_score = 0, 0
		for card in self.card_list:
			card.update_gem_score(self.mu_bar, self.team_CR, self.strength_per_pt_tap, 
								  team_base_bond_cskill_value, self.live, new_setting, sort=sort)
			team_base_score += card.card_base_score
			best_gem_score  += card.max_alloc_score
		return team_base_score, best_gem_score

	def find_optimal_gem_allocation_DP(self, add_trick=True):
		# Generate a dict to store index of different types of gems
		grade_append = {1:'(1st)', 2:'(2nd)', 3:'(3rd)'}
		attr, attr2 = self.live.attr, attr2_list[attr_list.index(self.live.attr)]
		gem_list  = [attr+' Kiss', attr+' Perfume']
		gem_list += [attr+x+grade for x in [' Ring ', ' Cross '] for grade in list(grade_append.values())]
		gem_list += [attr+x for x in [' Aura', ' Veil']]
		gem_list += [attr2+x for x in [' Charm', ' Heal'] for attr2 in attr2_list] + [attr2+' Trick']*add_trick
		gem_idx_dict = {v:k for k,v in enumerate(gem_list)}

		# Compute the highest possible gem score for each card to help to prune branch
		max_single_alloc_score = np.array([card.max_alloc_score for card in self.card_list])
		remain_max = max_single_alloc_score.sum()

		# Compute auxiliary info from card, grade, skill gem type
		# Count members in each grade and has each type of skills to help to merge branch
		card_aux = [{'grade_idx':None, 'charm_idx':None, 'heal_idx':None} for i in range(9)]
		grade_count, charm_count, heal_count = {'(1st)':0, '(2nd)':0, '(3rd)':0}, {k:0 for k in attr2_list}, {k:0 for k in attr2_list}
		for i, card in enumerate(self.card_list):
			if card.grade != '': 
				card_aux[i]['grade_idx'] = [gem_idx_dict[self.live.attr+' Ring '+card.grade], gem_idx_dict[self.live.attr+' Cross '+card.grade]]
				grade_count[card.grade] += 1
			if card.is_charm or card.is_heal:
				if card.is_charm:
					card_aux[i]['charm_idx'] = gem_idx_dict[card.attr2+' Charm']
					charm_count[card.attr2] += 1
				elif card.is_heal:
					card_aux[i]['heal_idx'] = gem_idx_dict[card.attr2+' Heal']
					heal_count[card.attr2] += 1

		# Mark a gem type as unlimited if
		# * the gem number is at least 9
		# * ring, cross of a grade is larger than number of team member in that grade
		# * charm, heal of a color is larger than number of team member with same color and associated skill
		gem_occupy = [np.Inf if self.owned_gem[gem] >= 9 else self.owned_gem[gem] for gem in gem_list]
		for grade in list(grade_append.values()):
			idx = gem_idx_dict[self.live.attr+' Ring '+grade]
			if gem_occupy[idx] >= grade_count[grade]: gem_occupy[idx] = np.Inf
			idx = gem_idx_dict[self.live.attr+' Cross '+grade]
			if gem_occupy[idx] >= grade_count[grade]: gem_occupy[idx] = np.Inf
		for attr2 in attr2_list:
			idx = gem_idx_dict[attr2+' Charm']
			if gem_occupy[idx] >= charm_count[attr2]: gem_occupy[idx] = np.Inf
			idx = gem_idx_dict[attr2+' Heal']
			if gem_occupy[idx] >= heal_count[attr2]: gem_occupy[idx] = np.Inf

		# Initialize trellis
		trellis, current_max_score = [ {tuple(gem_occupy):[[],0]} ], 0
		# Construct trellis
		for i in range(9):
			stage, card, aux = dict(), self.card_list[i], card_aux[i]
			# For each remain case in stage i-1 and each possible allocation in stage i
			for remain, (plan, cum_score) in trellis[-1].items():
				# If all remaining card uses highest score allocation and still get lower score than current max
				# Then simply prune this unpromising branch
				if cum_score+remain_max < current_max_score: continue
				remain = list(remain)
				for alloc in self.card_list[i].gem_alloc_list:
					# Construct new remain vector and check if it is feasible
					new_remain, violate = remain.copy(), False
					for gem in alloc.gems: 
						if 'Trick' in gem and not add_trick: continue
						idx = gem_idx_dict[gem]
						if new_remain[idx] > 0: new_remain[idx] -= 1
						else: violate = True; break
					if violate: continue
					# Check if there are some gem become unlimited, if set the remain to Inf to merge branches
					for j in range(len(new_remain)):
						# Remaining gem number larger than number of remaining members
						if new_remain[j] >= 9-i: new_remain[j] = np.Inf
					if card.grade != '':
						# When grade is None, the card rarity is N
						ring_idx, cross_idx = aux['grade_idx']
						if new_remain[ring_idx]  > grade_count[card.grade]: new_remain[ring_idx]  = np.Inf
						if new_remain[cross_idx] > grade_count[card.grade]: new_remain[cross_idx] = np.Inf
						if card.is_charm or card.is_heal:
							charm_idx, heal_idx = aux['charm_idx'], aux['heal_idx']
							if charm_idx is not None and new_remain[charm_idx] > charm_count[card.attr2]: new_remain[charm_idx] = np.Inf
							if heal_idx  is not None and new_remain[heal_idx]  > heal_count[card.attr2]:  new_remain[heal_idx]  = np.Inf
					# If the total score is larger than current max score, update it
					new_remain = tuple(new_remain)
					if stage.get(new_remain) is None or cum_score+alloc.score > stage[new_remain][1]:
						stage[new_remain] = [plan+[alloc], cum_score+alloc.score]
						if cum_score+alloc.score > current_max_score: current_max_score = cum_score+alloc.score
			# Update grade and skill count for remaining members
			if card.grade != '':
				grade_count[card.grade] -= 1
				if card.is_charm or card.is_heal:
					charm_count[card.attr2] -= aux['charm_idx'] is not None
					heal_count[card.attr2] -= aux['heal_idx'] is not None
			remain_max -= max_single_alloc_score[i]
			trellis.append(stage)

		# Find best allocation and its score
		x_opt, Qmax = [Alloc([])]*9, 0
		for _, (plan, cum_score) in trellis[-1].items():
			if cum_score > Qmax: x_opt, Qmax = plan, cum_score
		return x_opt, Qmax

	def find_optimal_gem_allocation_DC(self, add_trick=True):
		def recursion(alloc_info, Qmax_init=0, first_alloc=None, first_Q=None):
			# Find the most scarce gem type
			best_case, scarce_gem, max_lack = defaultdict(lambda:False), None, 0
			for i in range(9):
				for gem in alloc_info[i][0].gems: best_case[gem] += 1
			for gem, need_val in best_case.items():
				lack = best_case[gem] - self.owned_gem[gem]
				if lack > max_lack: scarce_gem, max_lack = gem, lack

			if scarce_gem is None:
				if first_Q is not None:
					# Best allocation for current problem is satisfied
					x_opt, Qmax = first_alloc, first_Q
				else:
					x_opt, Qmax = [x[0] for x in alloc_info], sum([x[0].score for x in alloc_info])
			else:
				# For each card, first compute the 'peeled' allocation list by dropping allocation containing the scarce gem
				peeled = [[ x for x in alloc_list if scarce_gem not in x.gems] for alloc_list in alloc_info]
				# Split current case into subproblems
				x_opt, Qmax = [Alloc([],0)]*9, Qmax_init
				for ind in itertools.combinations(valid_card_index[scarce_gem], self.owned_gem[scarce_gem]):
					# Construct subproblem
					sub_alloc_info = [alloc_info[i] if i in ind else peeled[i] for i in range(9)]
					# Compute the best allocation of subproblem
					first_alloc, first_Q = [x[0] for x in sub_alloc_info], sum([x[0].score for x in sub_alloc_info])
					# If the best allocation in subproblem has larger strength, then it is worth exploring
					if first_Q >= Qmax:
						x_sol, Qsol = recursion(sub_alloc_info, Qmax, first_alloc, first_Q)
						if Qsol > Qmax: x_opt, Qmax = x_sol, Qsol
			return x_opt, Qmax
		if add_trick:
			alloc_info = [card.gem_alloc_list for card in self.card_list]
		else:
			alloc_info = [[alloc for alloc in card.gem_alloc_list if 'Trick' not in str(alloc.gems)] for card in self.card_list]
		# For each considered SIS, compute list of card indices that can equip it
		valid_card_index = dict()
		for ind, alloc_list in enumerate(alloc_info):
			for alloc in alloc_list:
				if len(alloc.gems) == 1:
					gem = alloc.gems[0]
					if valid_card_index.get(gem) is None:
						valid_card_index[gem] = [ind]
					else:
						valid_card_index[gem].append(ind)
		x_opt, Qmax = recursion(alloc_info)
		return x_opt, Qmax

	def allocate(self, alloc_method='DP', max_score=0, add_trick_thresh=0.67):
		# Update score of gems
		team_base_score, best_gem_score = self.update_gem_score(sort=alloc_method=='DC')
		add_trick = int(self.team_CR > add_trick_thresh)
		# # If for unlimited gem the choice is worse than max_score, drop it
		if team_base_score + best_gem_score < max_score: return None
		# Solve for best gem allocation
		if alloc_method == 'DP':
			optimal_alloc, alloc_score = self.find_optimal_gem_allocation_DP(add_trick)
		elif alloc_method == 'DC':
			optimal_alloc, alloc_score = self.find_optimal_gem_allocation_DC(add_trick)
		# Compute total score
		self.optimal_alloc, self.total_score = optimal_alloc, team_base_score + alloc_score
		return self.optimal_alloc, self.total_score

	def construct_team(self):
		for card, alloc in zip(self.card_list, self.optimal_alloc):
			card.equip_gem(alloc.gems)
		# Put non-center card with less same group&color bonus at position with smaller combo weight fraction
		bonus_list  = sorted([(card.mu,i) for i,card in enumerate(self.card_list[1:])])
		weight_list = sorted([(self.live.combo_weight_fraction[i], i) for i in range(9) if i!=4])

		final_card_list = [None]*4 + [self.card_list[0]] + [None]*4
		for i in range(8): 
			final_card_list[weight_list[i][1]] = self.card_list[1:][bonus_list[i][1]]
		return Team(final_card_list)

	def view_optimal_details(self, show_cost=False, lang='EN', fixed_team=None):
		team = self.construct_team() if fixed_team is None else fixed_team

		col_name = { x:'<img src="{0}" width=25/>'.format(misc_path(x)) for x in ['level','bond','smile','pure','cool'] }

		columns  = ['CID', 'Icon', 'SIS', 'Skill Gain']
		columns += [col_name[x] for x in ['level', 'bond', 'smile', 'pure', 'cool']]
		columns += ['Single +', 'Single ×', 'Team ×', 'Card STR', 
					'Main-C', 'Vice-C', 'Main-C2', 'Vice-C2', 'Team STR', 'Judge STR',
					'Charm', 'Heal', 'Trick', 'Amend STR', 'Skill STR', 'Live Bonus', 'Cmb WT%']

		# Extract all team gems
		team_gems = [gem for card in team.card_list for gem in card.equipped_gems \
					 	if self.live.attr in gem.name and gem.effect == 'team_boost']
		# Find team center skill and cover rate
		cskill = team.center().cskill
		temp = np.ones(9)
		for i, card in enumerate(team.card_list):
			if card.skill is not None and card.skill.effect_type in ['Weak Judge', 'Strong Judge']:
				temp[i] -= card.skill.skill_gain(setting=self.setting)[0]
		CR = 1 - temp.prod()
		new_setting = self.setting.copy()
		new_setting['perfect_rate'] = 1 - (1-self.live.perfect_rate) * (1-self.team_CR)

		# Compute 
		bonus = lambda card: attr_match_factor**(self.live.attr==card.main_attr) * group_match_factor**(self.live.group in card.tags)
		attr_group_bonus = np.array([bonus(card) for card in team.card_list])
		mu_bar = (attr_group_bonus * self.live.combo_weight_fraction).sum()

		def get_summary(index, card):
			res = { 'CID':'<p>{0}</p>'.format(card.card_id), 
					'Icon': '<img src="{0}" style="width:100%;max-width:75px;" />'.format(icon_path(card.card_id, card.idolized)),
					'SIS':gem_slot_pic(card, show_cost=show_cost, gem_size=25)}

			# Skill gain information
			if card.skill is not None:
				gain = card.skill.skill_gain(setting=self.setting)[0]
				if card.skill.effect_type in ['Strong Judge', 'Weak Judge']:
					skill_gain_str = '{0:.2f}% covered '.format(100*card.CR)
				elif card.skill.effect_type == 'Stamina Restore':
					skill_gain_str = '{0:.3f} hp/note'.format(gain)
				elif card.skill.effect_type == 'Score Up':
					skill_gain_str = '{0:.2f} pt/note'.format(gain)
				fmt = '<p> <img style="float:left" src="{0}" width=15 /> Lv{1} <br clear="both"/> {2} </p>'
				res['Skill Gain'] = fmt.format(misc_path(card.skill.effect_type) ,card.skill.level, skill_gain_str)
			else:
				res['Skill Gain'] = '<p>{0}</p>'.format('NA')

			# Basic stats
			fmt = '<p style="color:{0};"> {1:<4d} </p>'
			res[col_name['level']] = fmt.format('black', card.level)
			res[col_name['bond']] = fmt.format(attr_color[card.main_attr], card.bond)
			for attr in attr_list:
				res[col_name[attr.lower()]] = fmt.format(attr_color[attr], getattr(card, attr.lower()))

			# Non-skill gem bonus
			base_value = { attr:getattr(card, attr.lower()) + card.bond*(attr==card.main_attr) for attr in attr_list }
			before_C_value = base_value.copy()
			single_plus, single_mult, team_mult = {k:0 for k in attr_list}, {k:0 for k in attr_list}, {k:0 for k in attr_list}
			for gem in card.equipped_gems:
				for attr in attr_list:
					if attr in gem.name:
						if gem.effect == 'attr_add': 
							single_plus[attr] += gem.value
						if gem.effect == 'attr_boost': 
							single_mult[attr] += math.ceil(base_value[attr] * gem.value/100)
			for gem in team_gems:
				for attr in attr_list:
					if attr in gem.name:
						team_mult[attr] += math.ceil(base_value[attr] * gem.value/100)
			for attr in attr_list:
				before_C_value[attr] += single_plus[attr] + single_mult[attr] + team_mult[attr]
			res['Single +'] = single_plus[self.live.attr]
			res['Single ×'] = single_mult[self.live.attr] 
			res['Team ×']   = team_mult[self.live.attr]
			res['Card STR'] = before_C_value[self.live.attr]

			# Center skill bonus and team strength
			res['Main-C'], res['Vice-C'], res['Main-C2'], res['Vice-C2'] = 0, 0, 0, 0
			if cskill is not None and cskill.main_attr == self.live.attr:
				res['Main-C'] += math.ceil(before_C_value[cskill.base_attr] * cskill.main_ratio/100)
				if cskill.bonus_ratio is not None and cskill.bonus_range in card.tags:
					res['Vice-C'] += math.ceil(res['Card STR'] * cskill.bonus_ratio/100)
			if self.guest_cskill is not None and self.guest_cskill.main_attr == self.live.attr:
				res['Main-C2'] += math.ceil(before_C_value[self.guest_cskill.base_attr] * self.guest_cskill.main_ratio/100)
				if self.guest_cskill.bonus_ratio is not None and self.guest_cskill.bonus_range in card.tags:
					res['Vice-C2'] += math.ceil(res['Card STR'] * self.guest_cskill.bonus_ratio/100)
			res['Team STR'] = res['Card STR'] + res['Main-C'] + res['Vice-C'] + res['Main-C2'] + res['Vice-C2']

			# Skill gem equivalent strength
			res['Charm'], res['Heal'], res['Trick'] = 0, 0, 0
			if card.skill is not None and card.skill.effect_type in ['Score Up', 'Stamina Restore']:
				skill_gain, strength_per_pt_tap = card.skill.skill_gain(setting=new_setting)
				if card.skill.effect_type == 'Score Up':
					res['Charm'] = math.ceil(skill_gain*strength_per_pt_tap)
					if any(['Charm' in gem.name for gem in card.equipped_gems]):
						res['Charm'] += math.ceil(1.5*skill_gain*strength_per_pt_tap)
				elif card.skill.effect_type == 'Stamina Restore' and any(['Heal' in gem.name for gem in card.equipped_gems]):
					res['Heal'] = math.ceil(480*skill_gain*strength_per_pt_tap)
			res['Judge STR'] = res['Team STR']
			if self.live.attr == card.main_attr and any(['Trick' in gem.name for gem in card.equipped_gems]):
				res['Trick'] = math.ceil((res['Card STR']-res['Team ×'])*0.33*self.team_CR)
				res['Judge STR'] += math.ceil((res['Card STR']-res['Team ×'])*0.33)
			res['Skill STR'], res['Amend STR'] = res['Charm']+res['Heal'], res['Team STR']+res['Trick']

			# Compute same group and same color bonus
			res['Live Bonus'] = '{0:.2f}'.format(bonus(card))
			res['Cmb WT%'] = '{0:.2f}%'.format(self.live.combo_weight_fraction[index]*100)
			return res

		# Data frame for detailed stats
		data = [get_summary(i, card) for i, card in enumerate(team.card_list)]
		df = pd.DataFrame(data, columns=columns)

		# Data frame for live song
		def format_song_name(name):
			s = name.split(': ')
			return [s[0] + ':'] + s[1].split(', ') if len(s) > 1 else s[0].split(', ')
		song_name = '<p style="color:{0};">{1}</p>'.format(attr_color[self.live.attr], '<br/>'.join(format_song_name(self.live.name)))
		df_live = pd.DataFrame({'Song Name': [song_name]})
		df_live['Difficulty'] = self.live.difficulty
		df_live['Total Note'] = self.live.note_number
		df_live['Duration'] = self.live.duration
		df_live['Pt per STR'] = self.live.pts_per_strength
		df_live['Presume PR'] = '{0:.2f}%'.format(self.live.perfect_rate*100)
		df_live['Score Up Rate'] = self.setting['score_up_rate']
		df_live['Skill Up Rate'] = self.setting['skill_up_rate']
		df_live['Avg Pos Bonus'] = mu_bar
		df_live.index = ['Live Stats']
		df_live.columns = ['<p>{0}</p>'.format(x) for x in list(df_live.columns)]
		df_live = df_live.applymap(lambda x: x if type(x)==str and x[0]=='<' else '<p>{0}</p>'.format(round(x,3) if type(x)==float else ('-' if str(x)=='0' else x)))
		if lang=='CN':
			df_live.columns = ['<p>{0}</p>'.format(x) for x in ['曲名', '难度', 'Note个数' ,'时长', '每点强度对应得分', '预设P率', '应援得分加成', '应援技能加成', '平均位置加成']]
		html_live = df_live.to_html(escape=False)

		# Data frame for brief team total stats
		def format_cskill(cskill):
			if cskill is None: return '<p>{0}</p>'.format('NA')
			fmt ='<img src="{0}" height=25 style="display:inline;vertical-align: middle;">'
			cskill_str  = '<div style="padding:5px">' + fmt.format(misc_path(cskill.main_attr.lower())) + '<span> + </span>'
			cskill_str += fmt.format(misc_path(cskill.base_attr.lower())) + '<span> x {0}% </span>'.format(cskill.main_ratio) + '</div>'
			if cskill.bonus_range is not None:
				cskill_str += '<div style="padding:5px">' + fmt.format(misc_path(cskill.bonus_range))
				cskill_str += fmt.format(misc_path(cskill.main_attr.lower())) + '<span> x {0}% </span>'.format(cskill.bonus_ratio) + '</div>'
			return cskill_str

		df_team = pd.DataFrame({'Center Skill':[format_cskill(team[4].cskill)], 'Guest Center Skill': [format_cskill(self.guest_cskill)]})
		df_team['Mics/OP'] = '{0} / {1}'.format(*team.compute_mics())
		df_team['Cover Rate'] = '{0:.2f}%'.format(self.team_CR*100)
		df_team['Team STR'] = df['Team STR'].sum()
		df_team['Amend Team STR'] = df['Amend STR'].sum()
		df_team['Total Skill STR'] = df['Skill STR'].sum()
		df_team['Expected Score']  = math.floor(df_team['Amend Team STR'] * self.live.pts_per_strength * mu_bar * self.setting['score_up_rate']) 
		df_team['Expected Score'] += math.floor(df_team['Total Skill STR'] * self.live.pts_per_strength)
		df_team.index = ['Total Stats']
		df_team.columns = ['<p>{0}</p>'.format(x) for x in list(df_team.columns)]
		df_team = df_team.applymap(lambda x: x if type(x)==str and x[0]=='<' else '<p>{0}</p>'.format(round(x,3) if type(x)==float else ('-' if str(x)=='0' else x)))
		if lang=='CN':
			df_team.columns = ['<p>{0}</p>'.format(x) for x in ['Center技', '好友Center技', 'Mic数／援力', '判定覆盖率' ,'队伍强度', '判定修正队伍强度', '总技能强度', '期望得分']]
		html_team = df_team.to_html(escape=False)

		df.columns = ['<p>{0}</p>'.format(x) if '<p>' not in x else x for x in columns]		
		df = df.applymap(lambda x: x if type(x)==str and x[0]=='<' else '<p>{0}</p>'.format('-' if type(x)==int and x==0 else x))
		df.index = ['<p>{0}</p>'.format(x) for x in ['L1', 'L2', 'L3', 'L4', 'C', 'R4', 'R3', 'R2', 'R1']]
		if lang=='CN':
			columns  = ['<p>{0}</p>'.format(x) for x in ['卡牌编号', '卡牌图标', '装配宝石' ,'技能收益']] + list(df.columns)[4:9]
			columns += ['<p>{0}</p>'.format(x) for x in ['单体增加宝石', '单体加成宝石', '团队加成宝石' ,'单卡界面强度', '队伍主C', '队伍副C', '好友主C', '好友副C', '单卡队中强度', 
						'单卡队中强度(判)', '得分技能强度', '回复技能强度', '判定技能强度', '单卡修正强度', '单卡技能强度', '同色同团加成', '连击权重占比']] 
			df.columns = columns
		html_main = df.transpose().to_html(escape=False)

		html_recommend_guest = ''
		if self.guest_cskill is None:
			# find all UR center skill with same color as the live
			raw_card_dict = {int(k):Card.fromJSON(v) for k,v in json.loads(open(card_archive_dir).read()).items()}
			guest_candidate, cskill_list = defaultdict(lambda:[]), []
			is_new = lambda cskill: all([not x.is_equal(cskill) for x in cskill_list])
			for index, card in raw_card_dict.items():
				if card.main_attr == self.live.attr and card.rarity == 'UR' and not card.promo:
					guest_candidate[(card.cskill.base_attr, card.cskill.bonus_range)].append(card.card_id)
					if is_new(card.cskill):
						cskill_list.append(card.cskill)
			# find the center skill that increases the team strength most
			best_guest_cskill, max_strength = None, 0
			for cskill in cskill_list:
				strength = team.team_strength(guest_cskill=cskill)['team_total'][attr_list.index(self.live.attr)]
				if strength > max_strength:
					best_guest_cskill, max_strength = cskill, strength
			recommend_guest = guest_candidate[(best_guest_cskill.base_attr, best_guest_cskill.bonus_range)]
			# construct data frame to demonstrate best guest center skill information
			df_guest = pd.DataFrame()
			df_guest['Recommend Guest Center Skill'] = [format_cskill(best_guest_cskill)]
			# list the cards that has the best guest center skill
			guest_size, fmt = 50, '<div style="float:left;*padding-left:0;"><img src="{0}" width={1}></div>'
			# divs = [fmt.format(icon_path(card_id,idolized), guest_size) for card_id in recommend_guest for idolized in [False,True] ]
			divs1 = [fmt.format(icon_path(card_id,False), guest_size) for card_id in recommend_guest]
			divs2 = [fmt.format(icon_path(card_id,True), guest_size) for card_id in recommend_guest]
			df_guest['Recommend Guest Icon'] = '<div style="width:{0}px;">{1}<div>'.format(len(divs1)*guest_size, ''.join(divs1)+''.join(divs2))
			# compute the expected score if the best guest center skill is present
			setting = self.setting.copy()
			setting.update({'score_up_bonus':setting['score_up_rate']-1, 'skill_up_bonus':setting['skill_up_rate']-1, 'guest_cskill':best_guest_cskill})
			df_guest['Expected Score'] = team.compute_expected_total_score(self.live, setting)
			df_guest.columns = ['<p>{0}</p>'.format(x) for x in list(df_guest.columns)]
			df_guest = df_guest.applymap(lambda x: x if type(x)==str and x[0]=='<' else '<p>{0}</p>'.format(round(x,3) if type(x)==float else ('-' if str(x)=='0' else x)))
			if lang=='CN':
				df_guest.columns = ['<p>{0}</p>'.format(x) for x in ['推荐好友Center技', '拥有该技能的卡牌图标' ,'应援后期望得分']]
			html_recommend_guest = df_guest.to_html(escape=False, index=False)

		return HTML(html_template.format(html_live+html_team+html_recommend_guest+html_main))

	def to_html(self, file_name, show_cost=True):
		html = self.view_optimal_details(show_cost=show_cost)
		with open(file_name, 'w') as fp:
			fp.write(html_template.format(html.data.replace('\n','')))