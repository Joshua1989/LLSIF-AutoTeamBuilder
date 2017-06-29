from llatb.common.global_var import *

# Default presumption: A live contain 700 notes and lasts for 120 seconds
# 10% notes are star note, 8% notes are long note, 4% notes are swing note
# Player has team with strength 80000, 95% of the taps are Perfect, the rest 5% are Great
default_setting = {	'note_number':700, 'duration':120, 'star_density':0.1, 'attr_group_factor':1.15,
					'note_type_dist':{'normal_density':0.88, 'long_density':0.08, 'swing_density':0.04}, 
					'perfect_rate':0.95, 'team_strength':80000, 'score_up_rate':1, 'skill_up_rate':1}
# Pre-calculate combo factor
pre_calc_combo_factor = np.array([combo_factor(i) for i in range(1,2001)]).cumsum() / np.arange(1,2001)

class Skill:
	def __init__(self, name=None, trigger_type=None, trigger_count=None, 
				 effect_type=None, odds_list=None, reward_list=None, level=1):
		self.name = None
		self.trigger_type, self.trigger_count = None, None
		self.effect_type, self.odds_list, self.reward_list = None, None, None
		self.level, self.max_level = level, 8
		self.odds, self.reward = 0, 0
		
		param = [name, trigger_type, trigger_count, effect_type, odds_list, reward_list]
		n_None = sum(map(lambda x: x is None, param))
		if n_None == len(param)-1:
			return
		elif n_None != 0 and n_None != len(param):
			print('The parameter must be all None or all not None!')
			raise
		self.name, self.level = name, level
		if trigger_type not in trigger_type_list:
			print('Incorrect skill trigger type!')
			raise
		self.trigger_type, self.trigger_count = trigger_type, trigger_count
		if effect_type not in effect_type_list:
			print('Incorrect skill reward type!'+effect_type)
			raise
		self.effect_type = effect_type
		if len(odds_list) != 8 or len(reward_list) != 8:
			print('The length of oddsability and reward must be 8!')
			raise
		self.odds_list, self.reward_list = odds_list, reward_list
		self.odds, self.reward = odds_list[level-1], reward_list[level-1]
	def __repr__(self):
		if self.name is None:
			return 'NA'
		else:
			head = '{0} lv{1}: '.format(self.name, self.level)
			odds_str = '{0}% chance to '.format(self.odds)
			effect_str = effect_str_dict[self.effect_type].format(self.reward)
			trigger_str = trigger_str_dict[self.trigger_type].format(self.trigger_count)
		return head + odds_str + effect_str + trigger_str
	def set_level(self, level):
		if level < 1 or level > 8 or round(level) != level:
			print('Skill level must be integer between 1 and 8!')
			raise
		else:
			self.level = level
			self.odds, self.reward = self.odds_list[level-1], self.reward_list[level-1]
	def skill_gain(self, setting=default_setting):
		# Set parameter for live and player performance
		param = default_setting.copy()
		param.update(setting)

		# Presumed live parameter
		note_number, duration = param['note_number'], param['duration']
		star_density   = param['star_density']
		normal_density = param['note_type_dist']['normal_density']
		long_density   = param['note_type_dist']['long_density']
		swing_density  = param['note_type_dist']['swing_density']
		# Presumed player parameter
		attr_group_factor = param['attr_group_factor']
		perfect_rate, team_strength = param['perfect_rate'], param['team_strength']
		score_up_rate, skill_up_rate = param['score_up_rate'], param['skill_up_rate']
		
		# Number of notes per second
		note_per_sec = note_number/duration 
		# Average combo factor if achieve FC
		combo_weight = pre_calc_combo_factor[note_number-1]
		# Average accuracy factor under presumed player perfect rate and live note type fractions
		note_judge_factor = perfect_rate*accuracy_factor['Perfect'] + (1-perfect_rate)*accuracy_factor['Great']
		note_judge_weight = note_judge_factor*(normal_density+swing_factor*swing_density) + note_judge_factor**2 * long_factor*long_density
		# Corrected strength per point per tap
		strength_per_pt_tap = 1 / (base_score_factor*combo_weight*note_judge_weight)
		# Average score per note = score_up_rate * presumed team strength / strength per point
		pt_per_note = score_up_rate * team_strength / strength_per_pt_tap
		

		# Set skill parameter
		trigger_type, effect_type = self.trigger_type, self.effect_type
		require, prob, reward = self.trigger_count, self.odds/100 * skill_up_rate, self.reward
		# Normalized expected reward per trigger unit (for Time trigger is per second, for Note trigger is per note, etc)
		norm_reward = reward*prob/require 	

		# If not amend: the computation will not account the case that skill is harder to trigger when it is near-end 
		# If amend: account the case that skill is harder to trigger when it is near-end 
		# i.e. multiplied by a factor depending on the loss rate for Score Up and Stamina Restore, 
		if effect_type in ['Weak Judge', 'Strong Judge']:
			if trigger_type == 'Time':
				gain = norm_reward / (norm_reward+1.0)
				loss_rate = 0.5 * ( (1-gain)*require + reward ) / duration
			elif trigger_type in ['Note', 'Combo']:
				gain = norm_reward * note_per_sec / ( 1 + prob * np.maximum(note_per_sec*reward/require-1,0) )
				loss_rate = np.mod(note_number, require) / note_number
		# For Stamina Restore skills, return 'hp recovered per note'
		elif effect_type == 'Stamina Restore':
			if trigger_type == 'Time':
				gain = norm_reward / note_per_sec
				loss_rate = np.mod(duration, require) / duration
			elif trigger_type in ['Note', 'Combo']:
				gain = norm_reward
				loss_rate = np.mod(note_number, require) / note_number
			elif trigger_type == 'Perfect':
				gain = norm_reward * perfect_rate
				loss_rate = 0.5 * require / (note_number*perfect_rate)
		# For Score Up skills, return 'extra score earned per note'
		elif effect_type == 'Score Up':
			if trigger_type == 'Time':
				gain = norm_reward / note_per_sec
				loss_rate = np.mod(duration, require) / duration
			elif trigger_type in ['Note', 'Combo']:
				gain = norm_reward
				loss_rate = np.mod(note_number, require) / note_number
			elif trigger_type == 'Perfect':
				gain = norm_reward * perfect_rate
				loss_rate = 0.5 * require / (note_number*perfect_rate)
			elif trigger_type == 'Score':
				gain = norm_reward/(1-norm_reward) * attr_group_factor * pt_per_note
				loss_rate = 0.5 * require / (attr_group_factor * pt_per_note * note_number)
			elif trigger_type == 'Star':
				gain = norm_reward * star_density * perfect_rate
				loss_rate = 1 if star_density==0 else 0.5 * require / (perfect_rate*star_density*note_number)
		gain *= 1 - loss_rate
		return gain, strength_per_pt_tap
		