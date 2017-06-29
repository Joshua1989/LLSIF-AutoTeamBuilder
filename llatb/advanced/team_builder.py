import numpy as np
import pandas as pd
from collections import defaultdict
import math, itertools
from llatb.common.global_var import *
from llatb.framework import card_dataframe, Team
from llatb.framework.live import Live, DefaultLive
from llatb.common.display import gem_slot_pic, view_cards
from llatb.common.config import misc_path, icon_path, gem_path
from llatb.simulator import Simulator
from IPython.display import HTML

class TeamBuilder:
	def __init__(self, live, game_data, opt={}):
		self.cards = game_data.raw_card
		self.owned_gem = game_data.owned_gem
		self.live = live
		self.guest_cskill = opt.get('guest_cskill',None)
		self.score_up_bonus = opt.get('score_up_bonus',0)
		self.skill_up_bonus = opt.get('skill_up_bonus',0)
		self.generate_setting(opt)
		self.best_team = None
	def generate_setting(self, opt={}):
		res = { key:getattr(self.live, key) for key in ['note_number', 'duration', 'star_density', 'note_type_dist', 'perfect_rate'] }
		res['attr_group_factor'] = 1
		res['team_strength'] = opt.get('rough_team_strength', 80000)
		res['score_up_rate'] = 1 + self.score_up_bonus
		res['skill_up_rate'] = 1 + self.skill_up_bonus
		self.setting = res
	def compute_rough_strength(self, cskill=None):
		# Compute rough strength and sort them by live attribute
		setting = self.setting.copy()
		setting.update({'cskill1':cskill, 'cskill2':self.guest_cskill, 'group_match':True})
		result = []
		for index, card in self.cards.items():
			setting['group_match'] = self.live.group in card.tags
			result.append((int(index), card, card.general_strength(setting=setting), False if card.cskill is None else card.cskill.is_equal(cskill)))
		result.sort(key=lambda x: x[2][self.live.attr]['strength'], reverse=True)
		return result
	def show_rough_strength(self, center_idx, head=None):
		result = self.compute_rough_strength(self.cards[str(center_idx)].cskill)
		data = []
		keys = [ 'card_id', 'member_name', 'main_attr',
				 'idolized', 'promo', 'rarity',
				 'level', 'max_level', 
				 'bond', 'max_bond', 
				 'hp', 'smile', 'pure', 'cool',
				 'skill', 'cskill', 
				 'slot_num', 'max_slot_num', 'equipped_gems', 'tags']
		columns  = ['index'] + keys + ['Same CSkill']
		columns += ['Rough '+attr for attr in attr_list] + ['Use Gem '+attr for attr in attr_list]
		for index, card, rough_strength, same_cskill in result:
			res = {k:getattr(card,k) for k in keys}
			res['index'] = index
			for attr in attr_list:
				res['Rough '+attr] = rough_strength[attr]['strength']
				res['Use Gem '+attr] = rough_strength[attr]['use_skill_gem']
			res['Same CSkill'] = same_cskill
			data.append(res)

		df = pd.DataFrame(data, columns=columns)
		df = df.set_index('index')
		df.index.name = ''
		# Sort cards according to live attribute and corresponding rough strength, put the center card at first
		df_center = df.loc[[center_idx]]
		df_rest = df.loc[[x for x in list(df.index) if x != center_idx]]
		df = df_center.append(df_rest)
		if head is not None:
			df = df.iloc[:head+1]
		return view_cards(df, extra_col=['Same CSkill']+[x+self.live.attr for x in ['Rough ', 'Use Gem ']])
	def list_gem_allocation(self, card):
		def unique(l):
			result, aux = list(), list()
			for x in l:
				if set(x) not in aux:
					result.append(x)
					aux.append(set(x))
			return result
		# Find all possible gem allocation
		attr, attr2 = self.live.attr, ['Princess', 'Angel', 'Empress'][attr_list.index(card.main_attr)]
		grade = ['('+x.replace('-year', ')') for x in card.tags if 'year' in x][0]
		gem_alloc = {0:[[]], 1:[[attr+' Kiss']], 2:[[attr+' Perfume'], [attr+' Ring '+grade]], 
					 3:[[attr+' Cross '+grade], [attr+' Aura']], 
					 4:[[attr+' Veil']], 5:[], 6:[], 7:[], 8:[]}
		if self.live.attr == card.main_attr:
			gem_alloc[4].append([attr2+' Trick'])
		if card.skill is not None:
			if card.skill.effect_type == 'Score Up':
				gem_alloc[4].append([attr2+' Charm'])
			elif card.skill.effect_type == 'Stamina Restore':
				gem_alloc[4].append([attr2+' Heal'])

		for i in range(3,card.slot_num+1):
			temp = []
			for j in range(math.ceil(i/2),i):
				alloc1, alloc2 = gem_alloc[j], gem_alloc[i-j]
				for item1 in alloc1:
					for item2 in alloc2:
						if set(item1)&set(item2) == set():
							temp.append(list(set(item1)|set(item2)))
			gem_alloc[i] += unique(temp)
		gem_alloc_list = [ [alloc,0] for k,v in gem_alloc.items() for alloc in v if k <= card.slot_num ]
		return gem_alloc_list
	def update_gem_score(self, team_info):
		# Compute Average Position Bonus
		bonus = lambda card: attr_match_factor**(self.live.attr==card.main_attr) * group_match_factor**(self.live.group in card.tags)
		mu = np.array([bonus(item['card']) for item in team_info[1:]])
		zeta = self.live.combo_weight_fraction.copy()[[0,1,2,3,5,6,7,8]]
		mu.sort()
		zeta.sort()
		mu_bar = bonus(team_info[0]['card']) * self.live.combo_weight_fraction[4] + (mu*zeta).sum()

		# Compute team total cover rate and base+bond attribute
		temp, base_bond_value = np.ones(9), np.zeros(9)
		for i, item in enumerate(team_info):
			card = item['card']
			base_bond_value[i] = getattr(card, self.live.attr.lower()) + card.bond * (card.main_attr==self.live.attr)
			if card.skill is not None and card.skill.effect_type in ['Weak Judge', 'Strong Judge']:
				temp[i] -= card.skill.skill_gain(setting=self.setting)[0]
		CR, team_base_bond_value = 1 - temp.prod(), base_bond_value.sum()

		# Update settings to compute skill gain of Skill Up and Stamina Restore skills
		new_setting = self.setting.copy()
		new_setting['attr_group_factor'] = mu_bar
		new_setting['perfect_rate'] = 1 - (1-self.live.perfect_rate) * (1-CR)

		# Compute gem score for each card
		cskill = team_info[0]['card'].cskill
		team_base_score, best_gem_score = 0, 0
		for i, item in enumerate(team_info):
			card = item['card']
			# Compute center skill bonus of the live attribute
			boost = self.live.pts_per_strength * mu_bar * self.setting['score_up_rate']
			cskill_bonus = 0
			if cskill is not None:
				if cskill.main_attr == self.live.attr:
					if cskill.base_attr == self.live.attr:
						cskill_bonus += cskill.main_ratio/100
					else:
						team_base_score += math.ceil(getattr(card,cskill.base_attr.lower())*boost*cskill.main_ratio/100)
					if cskill.bonus_ratio is not None:
						cskill_bonus += (cskill.bonus_range in card.tags) * cskill.bonus_ratio/100
			if self.guest_cskill is not None: 
				if self.guest_cskill.main_attr == self.live.attr:
					if self.guest_cskill.base_attr == self.live.attr:
						cskill_bonus += self.guest_cskill.main_ratio/100
					else:
						team_base_score += math.ceil(getattr(card,self.guest_cskill.base_attr.lower())*boost*self.guest_cskill.main_ratio/100)
					if self.guest_cskill.bonus_ratio is not None:
						cskill_bonus += (self.guest_cskill.bonus_range in card.tags) * self.guest_cskill.bonus_ratio/100
			team_base_score += math.ceil(base_bond_value[i]*boost*(1+cskill_bonus))
			# Compute the score of each gem
			attr, attr2 = self.live.attr, ['Princess', 'Angel', 'Empress'][attr_list.index(card.main_attr)]
			grade = ['('+x.replace('-year', ')') for x in card.tags if 'year' in x][0]
			gem_score = {attr +' Kiss'			:math.ceil(200*boost*(1+cskill_bonus)), 
						 attr +' Perfume'		:math.ceil(450*boost*(1+cskill_bonus)), 
						 attr +' Ring ' + grade	:math.ceil(base_bond_value[i]*0.1*boost*(1+cskill_bonus)), 
						 attr +' Cross '+ grade	:math.ceil(base_bond_value[i]*0.16*boost*(1+cskill_bonus)), 
						 attr +' Aura'			:math.ceil(team_base_bond_value*0.018*boost*(1+cskill_bonus)),
						 attr +' Veil'			:math.ceil(team_base_bond_value*0.024*boost*(1+cskill_bonus))}
			if self.live.attr == card.main_attr:
				gem_score[attr2+' Trick'] = math.ceil(0.33*CR*base_bond_value[i]*boost)
			if card.skill is not None and card.skill.effect_type in ['Score Up', 'Stamina Restore']:
				skill_gain, strength_per_pt_tap = card.skill.skill_gain(setting=new_setting)
				if card.skill.effect_type == 'Score Up':
					gem_score[attr2+' Charm'] = math.ceil(skill_gain*1.5*strength_per_pt_tap*self.live.pts_per_strength)
					team_base_score += math.ceil(skill_gain*strength_per_pt_tap*self.live.pts_per_strength)
				elif card.skill.effect_type == 'Stamina Restore':
					gem_score[attr2+' Heal'] = math.ceil(skill_gain*480*strength_per_pt_tap*self.live.pts_per_strength)
			# Compute the score of each gem allocation and store
			alloc_list = item['gem_alloc_list']
			for alloc in alloc_list:
				alloc[1] = 0
				# If allocation does not contain Trick gem, simply sum them up
				# If allocation contains Trick gem, add extra point from single card gems
				for gem in alloc[0]: alloc[1] += gem_score[gem]
				if attr2+' Trick' in alloc[0]:
					for gem in alloc[0]: 
						if gem.split()[1] in ['Kiss', 'Perfume', 'Ring', 'Cross']:
							alloc[1] += math.ceil(0.33*CR*gem_score[gem]/(1+cskill_bonus/100))
			# Sort all possible allocation by score
			alloc_list.sort(key=lambda x: x[1], reverse=True)
			# Compute team base
			best_gem_score += alloc_list[0][1]

		return team_info, team_base_score, best_gem_score, CR
	def find_optimal_gem_allocation_DP(self, alloc_info):
		def check_feasible(plan):
			remain = self.owned_gem.copy()
			for alloc in plan:
				for gem in alloc:
					remain[gem] -= 1
					if remain[gem] < 0:
						return False
			return True

		# Initialize trellis
		trellis = [[[[],[],0] for i in range(9)]]
		# Construct trellis
		for i in range(9):
			stage = []
			for alloc, score in alloc_info[i]:
				next_plan, next_score_list, next_cum_score = [], [], 0
				# For each allocation in stage i, find the next feasible step with maximum score
				for plan, score_list, cum_score in trellis[-1]:
					temp_plan, temp_score_list, temp_cum_score = plan+[alloc], score_list+[score], cum_score+score
					if temp_cum_score > next_cum_score and check_feasible(temp_plan):
						next_plan, next_score_list, next_cum_score = temp_plan, temp_score_list, temp_cum_score
				if len(next_plan) > 0:
					stage.append([next_plan, next_score_list, next_cum_score])
			trellis.append(stage)

		# Find best allocation and its score
		best_plan, best_score_list, Qmax = None, None, 0
		for plan, score_list, cum_score in trellis[-1]:
			if cum_score > Qmax:
				best_plan, best_score_list, Qmax = plan, score_list, cum_score
		x_opt = [[best_plan[i], best_score_list[i]] for i in range(9)]
		return x_opt, Qmax
	def find_optimal_gem_allocation_DC(self, alloc_info, Qmax_init=0, first_alloc=None, first_Q=None):
		# Find the most scarce gem type
		best_case, scarce_gem, max_lack = defaultdict(lambda:False), None, 0
		for i in range(9):
			for gem in alloc_info[i][0][0]: best_case[gem] += 1
		for gem, need_val in best_case.items():
			lack = best_case[gem] - self.owned_gem[gem]
			if lack > max_lack: scarce_gem, max_lack = gem, lack

		if scarce_gem is None:
			if first_Q is not None:
				# Best allocation for current problem is satisfied
				x_opt, Qmax = first_alloc, first_Q
			else:
				x_opt, Qmax = [x[0] for x in alloc_info], sum([x[0][1] for x in alloc_info])
		else:
			# For each card, first compute the 'peeled' allocation list by dropping allocation containing the scarce gem
			peeled = [[ x for x in alloc_list if scarce_gem not in x[0]] for alloc_list in alloc_info]
			# Split current case into subproblems
			x_opt, Qmax = [[[],0]]*9, Qmax_init
			for ind in itertools.combinations(list(range(9)), self.owned_gem[scarce_gem]):
				# Construct subproblem
				sub_alloc_info = [alloc_info[i] if i in ind else peeled[i] for i in range(9)]
				# Compute the best allocation of subproblem
				first_alloc, first_Q = [x[0] for x in sub_alloc_info], sum([x[0][1] for x in sub_alloc_info])
				# If the best allocation in subproblem has larger strength, then it is worth exploring
				if first_Q > Qmax:
					x_sol, Qsol = self.find_optimal_gem_allocation_DC(sub_alloc_info, Qmax, first_alloc, first_Q)
					if Qsol > Qmax: x_opt, Qmax = x_sol, Qsol
		return x_opt, Qmax
	def build_team_fix_cskill(self, cskill, K=15, method='4-suboptimal', alloc_method='DP'):
		def find_candidates(cskill, K):
			# Compute rough strength
			rough_strength_info = self.compute_rough_strength(cskill=cskill)
			# Find the best card and choose it to be the center, and find K best cards from the rest for candidates
			center, candidates, k = None, [], 0
			for index, card, rough_strength, same_cskill in rough_strength_info:
				if same_cskill and center is None:
					center = {'index':index, 'card':card, 
							  'rough_strength':rough_strength[self.live.attr]['strength'],
							  'gem_alloc_list':self.list_gem_allocation(card)}
				elif k < K:
					candidates.append({'index':index, 'card':card, 
									   'rough_strength':rough_strength[self.live.attr]['strength'],
									   'gem_alloc_list':self.list_gem_allocation(card)})
					k += 1
				if center is not None and k >= K: break
			if center is None:
				print('There is no card has center skill', cskill)
				raise
			return center, candidates
		def single_case(choice, center, candidates, max_score=0):
			# Assemble a new team
			team_info = ([center] + [candidates[i] for i in choice]).copy()
			# Update score of gems
			team_info, team_base_score, best_gem_score, CR = self.update_gem_score(team_info)
			# If the best possible score is less than max score, drop this case
			if team_base_score + best_gem_score < max_score: return None
			# Solve for best gem allocation
			if alloc_method == 'DP':
				alloc_info, alloc_score = self.find_optimal_gem_allocation_DP([item['gem_alloc_list'] for item in team_info])
			elif alloc_method == 'DC':
				alloc_info, alloc_score = self.find_optimal_gem_allocation_DC([item['gem_alloc_list'] for item in team_info])
			# Compute total score
			total_score = team_base_score + alloc_score
			return team_info, alloc_info, total_score, CR
		def construct_team(team_info, alloc_info, CR):
			card_list, alloc = [item['card'].copy() for item in team_info], [item[0] for item in alloc_info]
			for card, gems in zip(card_list, alloc): card.equip_gem(gems)
			# Put non-center card with less same group&color bonus at position with smaller combo weight fraction
			bonus = lambda card: attr_match_factor**(self.live.attr==card.main_attr) * group_match_factor**(self.live.group in card.tags)
			bonus_list  = sorted([(bonus(card),i) for i,card in enumerate(card_list[1:],1)])
			weight_list = sorted([(self.live.combo_weight_fraction[i], i) for i in range(9) if i!=4])

			final_card_list = [None]*9
			final_card_list[4] = card_list[0]
			for i in range(8): final_card_list[weight_list[i][1]] = card_list[bonus_list[i][1]]
			return Team(final_card_list)
		
		center, candidates = find_candidates(cskill, K)
		if method == 'brute':
			max_score, best_team = 0, None
			for choice in itertools.combinations(list(range(K)), 8):
				result = single_case(choice, center, candidates, max_score)
				if result is None: continue
				team_info, alloc_info, total_score, CR = result
				if total_score > max_score:
					max_score, best_team = total_score, construct_team(team_info, alloc_info, CR)
		elif '-suboptimal' in method:
			t = int(method.replace('-suboptimal', ''))
			if t not in list(range(1,9)): 
				print('Suboptimal step must be in {1,...,8}')
				raise

			max_score, best_team, best_alloc = 0, None, None
			# Use a map to keep track of computed team to avoid duplicated computation
			score_map = defaultdict(lambda:0)
			# Initialize queue
			choice = tuple(list(range(8)))
			team_info, alloc_info, total_score, CR = single_case(choice, center, candidates)
			score_map[choice] = total_score
			max_score, best_team = total_score, construct_team(team_info, alloc_info, CR)
			queue = [choice]

			while len(queue) > 0:
				choice = queue.pop(0)
				rest = [x for x in range(K) if x not in choice]
				for tt in range(t):
					for pos in itertools.combinations(list(range(8)), tt):
						neighbor = list(choice)
						for new_idx in itertools.combinations(rest, tt):
							for i in range(tt): neighbor[pos[i]] = new_idx[i]
							new_choice = tuple(neighbor)
							if score_map[new_choice] == 0:
								res = single_case(new_choice, center, candidates, score_map[choice])
								if res is None: 
									score_map[new_choice] = 1
									continue
								team_info, alloc_info, total_score, CR = res
								score_map[new_choice] = total_score
								if total_score > max_score:
									max_score, best_team = total_score, construct_team(team_info, alloc_info, CR)
							elif score_map[new_choice] > score_map[choice] and new_choice not in queue:
								queue.append(new_choice)
		else:
			print('Unrecognized method {0}, only support brute and t-suboptimal'.format(method))
			raise		
		return max_score, best_team
	def build_team(self, K=15, method='4-suboptimal', alloc_method='DP'):
		def find_candidate_cskill():
			# Enumerate center skill of the highest rarity card that have same attribute with live
			rarity_list = ['UR','SSR','SR','R']
			cskill_dict = {rarity:[] for rarity in rarity_list}
			is_new = lambda rarity, cskill: all([not x.is_equal(cskill) for x in cskill_dict[rarity]])
			for index, card in self.cards.items():
				if card.main_attr != self.live.attr or card.rarity not in rarity_list: continue
				rarity, cskill = 'R' if card.promo else card.rarity, card.cskill
				if is_new(rarity, cskill): 
					cskill_dict[rarity].append(cskill)
			candidate_cskill = [None]
			for rarity in rarity_list:
				if len(cskill_dict[rarity]) > 0:
					candidate_cskill = cskill_dict[rarity]
					break
			return candidate_cskill

		cskill_list, result = find_candidate_cskill(), []
		max_score, best_team = 0, None
		print('Consider center skill in', [str(cskill) for cskill in cskill_list])
		for cskill in cskill_list:
			score, team = self.build_team_fix_cskill(cskill=cskill, K=K, method=method, alloc_method=alloc_method)
			result.append((score, team))
			print('Best team has score {0:6d} for {1}'.format(score, cskill))
			if score > max_score:
				max_score, best_team = score, team

		opt = {'skill_up_bonus':self.skill_up_bonus, 'score_up_bonus':self.score_up_bonus, 'guest_cskill':self.guest_cskill}
		self.best_team = best_team
		return self.show_best_team_stats()

	def show_best_team_stats(self):
		if self.best_team is None:
			print('The best team has not been formed yet')
			return
		col_name = { x:'<img src="{0}" width=25/>'.format(misc_path(x)) for x in ['level','bond','smile','pure','cool'] }

		columns  = ['CID', 'Icon', 'Gem', 'Skill Gain']
		columns += [col_name[x] for x in ['level', 'bond', 'smile', 'pure', 'cool']]
		columns += ['Single +', 'Single ×', 'Team ×', 'Card STR', 
					'Main-C', 'Vice-C', 'Main-C2', 'Vice-C2', 'Team STR', 'Judge STR',
					'Charm', 'Heal', 'Trick', 'Amend STR', 'Skill STR', 'Live Bonus', 'Cmb WT%', 'True STR']

		# Extract all team gems
		team_gems = [gem for card in self.best_team.card_list for gem in card.equipped_gems \
					 	if card.main_attr in gem.name and gem.effect == 'team_boost']
		# Find team center skill and cover rate
		cskill = self.best_team[4].cskill
		temp = np.ones(9)
		for i, card in enumerate(self.best_team.card_list):
			if card.skill is not None and card.skill.effect_type in ['Weak Judge', 'Strong Judge']:
				temp[i] -= card.skill.skill_gain(setting=self.setting)[0]
		CR = 1 - temp.prod()
		new_setting = self.setting.copy()
		new_setting['perfect_rate'] = 1 - (1-self.live.perfect_rate) * (1-CR)

		# Compute 
		bonus = lambda card: attr_match_factor**(self.live.attr==card.main_attr) * group_match_factor**(self.live.group in card.tags)
		attr_group_bonus = np.array([bonus(card) for card in self.best_team.card_list])
		mu_bar = (attr_group_bonus * self.live.combo_weight_fraction).sum()

		def get_summary(index, card):
			res = { 'CID':'<p>{0}</p>'.format(card.card_id), 
					'Icon': '<img src="{0}" width=75 />'.format(icon_path(card.card_id, card.idolized)),
					'Gem':gem_slot_pic(card, show_cost=False, gem_size=25)}

			# Skill gain information
			if card.skill is not None:
				gain = card.skill.skill_gain()[0]
				if card.skill.effect_type in ['Strong Judge', 'Weak Judge']:
					skill_gain_str = '{0:.2f}% covered '.format(100*gain)
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
				res['Trick'] = math.ceil((res['Card STR']-res['Team ×'])*0.33*CR)
				res['Judge STR'] += math.ceil((res['Card STR']-res['Team ×'])*0.33)
			res['Skill STR'], res['Amend STR'] = res['Charm']+res['Heal'], res['Team STR']+res['Trick']

			# Compute same group and same color bonus
			res['Live Bonus'] = '{0:.2f}'.format(bonus(card))
			res['Cmb WT%'] = '{0:.2f}%'.format(self.live.combo_weight_fraction[index]*100)

			# Compute true score including all multipliers
			res['True STR']  = math.ceil((res['Charm'] + res['Heal']) * self.live.average_bonus)
			res['True STR'] += math.ceil((res['Team STR']+res['Trick']) * mu_bar * self.live.average_bonus * self.setting['score_up_rate'])
			return res

		# Data frame for detailed stats
		data = [get_summary(i, card) for i, card in enumerate(self.best_team.card_list)]
		df = pd.DataFrame(data, columns=columns)

		# Data frame for live song
		song_name = '<p style="color:{0};">{1}</p>'.format(attr_color[self.live.attr], self.live.name)
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
		html_live = df_live.to_html(escape=False)

		# Data frame for brief team total stats
		df_team = pd.DataFrame({'Center Skill':[str(self.best_team[4].cskill)], 'Guest Center Skill': [str(self.guest_cskill)]})
		df_team['Cover Rate'] = '{0:.2f}%'.format(CR*100)
		df_team['Team STR'] = df['Team STR'].sum()
		df_team['Amend Team STR'] = df['Amend STR'].sum()
		df_team['Total Skill STR'] = df['Skill STR'].sum()
		df_team['Expected Score'] = math.floor(df['True STR'].sum() * base_score_factor) * self.live.note_number
		df_team.index = ['Total Stats']
		html_team = df_team.to_html(escape=False)

		df.columns = ['<p>{0}</p>'.format(x) if '<p>' not in x else x for x in columns]		
		df = df.applymap(lambda x: x if type(x)==str and x[0]=='<' else '<p>{0}</p>'.format('-' if type(x)==int and x==0 else x))
		df.index = ['<p>{0}</p>'.format(x) for x in ['L1', 'L2', 'L3', 'L4', 'C', 'R4', 'R3', 'R2', 'R1']]
		html_main = df.transpose().to_html(escape=False)

		return HTML(html_live+html_team+html_main)

	def simulate(self, boosts={}, save_to=None):
		if type(self.live) == DefaultLive:
			print('Cannot simulate under default live setting')
			return
		if self.best_team is None:
			print('The best team has not been formed yet')
			return

		param = {'Skill Up':self.skill_up_bonus, 'Tap Score Up':self.score_up_bonus, 'Perfect Support':0}
		param.update(boosts)
		sim = Simulator(self.best_team, guest_cskill=self.guest_cskill, boosts=param)
		song_name, difficulty, PR = self.live.name, self.live.difficulty, self.live.perfect_rate
		return sim.simulate(song_name, difficulty, prob=[PR,1-PR,0,0,0], save_to=save_to)