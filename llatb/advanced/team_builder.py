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
	def list_gem_allocation(self, card, no_kiss=False):
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
		gem_alloc = {0:[[]], 1:[[]] if no_kiss else [[attr+' Kiss']], 
					 2:[[attr+' Perfume'], [attr+' Ring '+grade]], 
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
				if no_kiss and  i-j == 1: continue
				alloc1, alloc2 = gem_alloc[j], gem_alloc[i-j]
				for item1 in alloc1:
					for item2 in alloc2:
						if set(item1)&set(item2) == set():
							temp.append(list(set(item1)|set(item2)))
			gem_alloc[i] += unique(temp)
		gem_alloc_list = [ [alloc,0] for k,v in gem_alloc.items() for alloc in v if k <= card.slot_num ]
		return gem_alloc_list
	def compute_card_stats(self, center, card):
		res = dict()
		# Compute same group & same color bonus
		res['mu'] = attr_match_factor**(self.live.attr==card.main_attr) * group_match_factor**(self.live.group in card.tags)
		# Compute judge cover rate
		res['CR'] = 0 if card.skill is None or card.skill.effect_type not in ['Weak Judge', 'Strong Judge'] else card.skill.skill_gain(setting=self.setting)[0]
		# Compute center skill bonus and card base score before same group & same color bonus
		partial_boost = self.live.pts_per_strength * self.setting['score_up_rate']
		res['base_bond_value'] = getattr(card, self.live.attr.lower()) + card.bond * (card.main_attr==self.live.attr) 
		res['cskill_bonus'], res['base_score'] = 0, 0
		if center.cskill is not None:
			if center.cskill.main_attr == self.live.attr:
				if center.cskill.base_attr == self.live.attr:
					res['cskill_bonus'] += center.cskill.main_ratio/100
				else:
					res['base_score'] += getattr(card,center.cskill.base_attr.lower())*partial_boost*center.cskill.main_ratio/100
				if center.cskill.bonus_ratio is not None:
					res['cskill_bonus'] += (center.cskill.bonus_range in card.tags) * center.cskill.bonus_ratio/100
		if self.guest_cskill is not None: 
			if self.guest_cskill.main_attr == self.live.attr:
				if self.guest_cskill.base_attr == self.live.attr:
					res['cskill_bonus'] += self.guest_cskill.main_ratio/100
				else:
					res['base_score'] += getattr(card,self.guest_cskill.base_attr.lower())*partial_boost*self.guest_cskill.main_ratio/100
				if self.guest_cskill.bonus_ratio is not None:
					res['cskill_bonus'] += (self.guest_cskill.bonus_range in card.tags) * self.guest_cskill.bonus_ratio/100
		res['base_score'] += res['base_bond_value']*partial_boost*(1+res['cskill_bonus'])
		# For skills that are not Score or Perfect or Star Perfect triggered, we do not need to compute it again
		if card.skill is not None and card.skill.effect_type in ['Score Up', 'Stamina Restore']:
			if card.skill.trigger_type not in ['Score', 'Perfect', 'Star']:
				skill_gain = card.skill.skill_gain(setting=self.setting)[0]
				if card.skill.effect_type == 'Score Up':
					res['skill_gain'] = skill_gain
				elif card.skill.effect_type == 'Stamina Restore':
					res['skill_gain'] = skill_gain
		return res
	def update_gem_score(self, team_info, sort=False):
		# Compute Average Position Bonus
		mu = np.array([item['stats']['mu'] for item in team_info[1:]])
		zeta = self.live.combo_weight_fraction.copy()[[0,1,2,3,5,6,7,8]]
		mu.sort()
		zeta.sort()
		mu_bar = team_info[0]['stats']['mu'] * self.live.combo_weight_fraction[4] + (mu*zeta).sum()
		# Compute team total cover rate
		CR = 1 - (1-np.array([item['stats']['CR'] for item in team_info])).prod()
		# Update settings to compute skill gain of Skill Up and Stamina Restore skills
		new_setting = self.setting.copy()
		new_setting['attr_group_factor'] = mu_bar
		new_setting['perfect_rate'] = 1 - (1-self.live.perfect_rate) * (1-CR)
		# Compute strength per tap after amending perfect rate
		for item in team_info:
			if item['card'].skill is not None:
				strength_per_pt_tap = item['card'].skill.skill_gain(setting=new_setting)[1]

		cskill_bonus = np.array([item['stats']['cskill_bonus'] for item in team_info])
		base_bond_value = np.array([item['stats']['base_bond_value'] for item in team_info])
		team_base_bond_value = base_bond_value.sum()
		# Compute gem score for each card
		boost = self.live.pts_per_strength * mu_bar * self.setting['score_up_rate']
		team_base_score, best_gem_score = 0, 0
		for i, item in enumerate(team_info):
			card, stats = item['card'], item['stats']
			team_base_score += math.ceil(stats['base_score']*mu_bar)
			# Compute the score of each gem
			attr, attr2 = self.live.attr, ['Princess', 'Angel', 'Empress'][attr_list.index(card.main_attr)]
			grade = ['('+x.replace('-year', ')') for x in card.tags if 'year' in x][0]
			gem_score = {attr +' Kiss'			:math.ceil(200*boost*(1+cskill_bonus[i])), 
						 attr +' Perfume'		:math.ceil(450*boost*(1+cskill_bonus[i])), 
						 attr +' Ring ' + grade	:math.ceil(base_bond_value[i]*0.1*boost*(1+cskill_bonus[i])), 
						 attr +' Cross '+ grade	:math.ceil(base_bond_value[i]*0.16*boost*(1+cskill_bonus[i])), 
						 attr +' Aura'			:math.ceil(team_base_bond_value*0.018*boost*(1+cskill_bonus[i])),
						 attr +' Veil'			:math.ceil(team_base_bond_value*0.024*boost*(1+cskill_bonus[i]))}
			if self.live.attr == card.main_attr:
				gem_score[attr2+' Trick'] = math.ceil(0.33*CR*base_bond_value[i]*boost)
			if card.skill is not None and card.skill.effect_type in ['Score Up', 'Stamina Restore']:
				if card.skill.trigger_type in ['Score', 'Perfect', 'Star']:
					skill_gain = card.skill.skill_gain(setting=new_setting)[0]
					if card.skill.effect_type == 'Score Up':
						gem_score[attr2+' Charm'] = math.ceil(skill_gain*1.5*strength_per_pt_tap*self.live.pts_per_strength)
						team_base_score += math.ceil(skill_gain*strength_per_pt_tap*self.live.pts_per_strength)
					elif card.skill.effect_type == 'Stamina Restore':
						gem_score[attr2+' Heal'] = math.ceil(skill_gain*480*strength_per_pt_tap*self.live.pts_per_strength)
				else:
					if card.skill.effect_type == 'Score Up':
						gem_score[attr2+' Charm'] = math.ceil(stats['skill_gain']*1.5*strength_per_pt_tap*self.live.pts_per_strength)
						team_base_score += math.ceil(stats['skill_gain']*strength_per_pt_tap*self.live.pts_per_strength)
					elif card.skill.effect_type == 'Stamina Restore':
						gem_score[attr2+' Heal'] = math.ceil(stats['skill_gain']*480*strength_per_pt_tap*self.live.pts_per_strength)
			# Compute the score of each gem allocation and store
			stats['gem_score'] = gem_score
			alloc_list, max_alloc_score = item['gem_alloc_list'], 0
			for alloc in alloc_list:
				alloc[1] = 0
				# If allocation does not contain Trick gem, simply sum them up
				# If allocation contains Trick gem, add extra point from single card gems
				for gem in alloc[0]: alloc[1] += gem_score[gem]
				if attr2+' Trick' in alloc[0]:
					for gem in alloc[0]: 
						if gem.split()[1] in ['Kiss', 'Perfume', 'Ring', 'Cross']:
							alloc[1] += math.ceil(0.33*CR*gem_score[gem]/(1+cskill_bonus[i]/100))
				if alloc[1] > max_alloc_score:
					max_alloc_score = alloc[1]
			# Compute total gem score
			best_gem_score += max_alloc_score
			# Sort all possible allocation by score
			if sort: alloc_list.sort(key=lambda x: x[1], reverse=True)
		return team_info, team_base_score, best_gem_score, CR
	def find_candidates(self, cskill, K, no_kiss=False):
		# Compute rough strength
		rough_strength_info = self.compute_rough_strength(cskill=cskill)
		# Find the best card and choose it to be the center, and find K best cards from the rest for candidates
		center, candidates, k = None, [], 0
		for index, card, rough_strength, same_cskill in rough_strength_info:
			if same_cskill and center is None:
				center = {'index':index, 'card':card, 
						  'rough_strength':rough_strength[self.live.attr]['strength'],
						  'gem_alloc_list':self.list_gem_allocation(card, no_kiss=no_kiss)}
			elif k < K:
				candidates.append({'index':index, 'card':card, 
								   'rough_strength':rough_strength[self.live.attr]['strength'],
								   'gem_alloc_list':self.list_gem_allocation(card, no_kiss=no_kiss)})
				k += 1
			if center is not None and k >= K: break
		if center is None:
			print('There is no card has center skill', cskill)
			raise
		else:
			center['stats'] = self.compute_card_stats(center['card'], center['card'])
			for card_info in candidates:
				card_info['stats'] = self.compute_card_stats(center['card'], card_info['card'])
		return center, candidates
	def find_optimal_gem_allocation_DP(self, team_info):
		alloc_info = [item['gem_alloc_list'] for item in team_info]
		# Compute the highest possible gem score for each card to help to prune branch
		max_single_alloc_score = np.zeros(9)
		for i in range(9):
			for alloc, score in alloc_info[i]:
				if score > max_single_alloc_score[i]:
					max_single_alloc_score[i] = score
		remain_max = max_single_alloc_score.sum()

		# Compute auxiliary info from card, grade, skill gem type
		attr2_list, grade_append = ['Princess', 'Angel', 'Empress'], [('(1st)'), '(2nd)', '(3rd)']
		card_aux = [{'grade':None, 'grade_idx':None, 'attr2':None, 'charm_idx':None, 'heal_idx':None} for i in range(9)]
		# Count members in each grade and has each type of skills to help to merge branch
		grade_count, charm_count, heal_count = np.zeros(3), np.zeros(3), np.zeros(3)
		for i, item in enumerate(team_info):
			card = item['card']
			grade = [int(tag[0]) for tag in card.tags if '-year' in tag]
			if len(grade) > 0: 
				card_aux[i]['grade'], grade_str = grade[0]-1, grade_append[grade[0]-1]
				card_aux[i]['grade_idx'] = [self.gem_rev_dict[self.live.attr+' Ring '+grade_str], 
									 		self.gem_rev_dict[self.live.attr+' Cross '+grade_str]]
				grade_count[card_aux[i]['grade']] += 1
			if card.skill is not None and card.skill.effect_type in ['Score Up', 'Stamina Restore']:
				card_aux[i]['attr2'] = attr_list.index(team_info[i]['card'].main_attr)
				attr2 = attr2_list[card_aux[i]['attr2']]
				if card.skill.effect_type == 'Score Up':
					card_aux[i]['charm_idx'] = self.gem_rev_dict[attr2+' Charm']
					charm_count[card_aux[i]['charm_idx']-self.gem_rev_dict['Princess Charm']] += 1
				elif card.skill.effect_type == 'Stamina Restore':
					card_aux[i]['heal_idx'] = self.gem_rev_dict[attr2+' Heal']
					charm_count[card_aux[i]['heal_idx']-self.gem_rev_dict['Princess Heal']] += 1

		# Mark a gem type as unlimited if
		# * the gem number is at least 9
		# * ring, cross of a grade is larger than number of team member in that grade
		# * charm, heal of a color is larger than number of team member with same color and associated skill
		gem_occupy = [np.Inf if x >= 9 else x for x in self.gem_occupy]
		for i, grade in enumerate(grade_append):
			idx = self.gem_rev_dict[self.live.attr+' Ring '+grade]
			if gem_occupy[idx] >= grade_count[i]: gem_occupy[idx] = np.Inf
			idx = self.gem_rev_dict[self.live.attr+' Cross '+grade]
			if gem_occupy[idx] >= grade_count[i]: gem_occupy[idx] = np.Inf
		for i, attr2 in enumerate(attr2_list):
			idx = self.gem_rev_dict[attr2+' Charm']
			if gem_occupy[idx] >= charm_count[i]: gem_occupy[idx] = np.Inf
			idx = self.gem_rev_dict[attr2+' Heal']
			if gem_occupy[idx] >= heal_count[i]: gem_occupy[idx] = np.Inf

		# Initialize trellis
		trellis, current_max_score = [ {tuple(gem_occupy):[[],[],0]} ], 0
		# Construct trellis
		for i in range(9):
			stage, aux = dict(), card_aux[i]
			# For each remain case in stage i-1 and each possible allocation in stage i
			for remain, (plan, score_list, cum_score) in trellis[-1].items():
				# If all remaining card uses highest score allocation and still get lower score than current max
				# Then simply prune this unpromising branch
				if cum_score+remain_max < current_max_score: continue
				remain = list(remain)
				for alloc, score in alloc_info[i]:
					# Construct new remain vector and check if it is feasible
					new_remain, violate = remain.copy(), False
					for gem in alloc: 
						idx = self.gem_rev_dict[gem]
						if new_remain[idx] > 0: new_remain[idx] -= 1
						else: violate = True; break
					if violate: continue
					# Check if there are some gem become unlimited, if set the remain to Inf to merge branches
					for j in range(len(new_remain)):
						# Remaining gem number larger than number of remaining members
						if new_remain[j] >= 9-i: new_remain[j] = np.Inf
					if aux['grade'] is not None:
						# When grade is None, the card rarity is N
						grade_idx, (ring_idx, cross_idx) = aux['grade'], aux['grade_idx']
						if new_remain[ring_idx]  > grade_count[grade_idx]: new_remain[ring_idx]  = np.Inf
						if new_remain[cross_idx] > grade_count[grade_idx]: new_remain[cross_idx] = np.Inf
						if aux['attr2'] is not None:
							# When attr2 is not None, the card has Score Up or Stamina Restore skill
							attr2_idx, charm_idx, heal_idx = aux['attr2'], aux['charm_idx'], aux['heal_idx']
							if charm_idx is not None and new_remain[charm_idx] > charm_count[attr2_idx]: new_remain[charm_idx] = np.Inf
							if heal_idx  is not None and new_remain[heal_idx]  > heal_count[attr2_idx]:  new_remain[heal_idx]  = np.Inf
					# If the total score is larger than current max score, update it
					new_remain = tuple(new_remain)
					if stage.get(new_remain) is None or cum_score+score > stage[new_remain][2]:
						stage[new_remain] = [plan+[alloc], score_list+[score], cum_score+score]
						if cum_score+score > current_max_score: current_max_score = cum_score+score
			# Update grade and skill count for remaining members
			if aux['grade'] is not None:
				grade_count[aux['grade']] -= 1
				if aux['attr2'] is not None:
					charm_count[aux['attr2']] -= aux['charm_idx'] is not None
					heal_count[aux['attr2']] -= aux['heal_idx'] is not None
			remain_max -= max_single_alloc_score[i]
			trellis.append(stage)

		# Find best allocation and its score
		best_plan, best_score_list, Qmax = [[]]*9, [0]*9, 0
		for remain, (plan, score_list, cum_score) in trellis[-1].items():
			if cum_score > Qmax:
				best_remain = remain
				best_plan, best_score_list, Qmax = plan, score_list, cum_score

		# Since in DP we first exclude all Kiss gem, if there is any card with remaining slot, equip Kiss to it
		kiss_gem = self.live.attr+' Kiss'
		remain_kiss = self.owned_gem[kiss_gem]
		for i in range(9):
			item, stats = team_info[i], team_info[i]['stats']
			best_plan[i] = best_plan[i].copy()
			slot_num = item['card'].slot_num
			alloc_cost = sum([gem_skill_dict[gem]['cost'] for gem in best_plan[i]])
			if alloc_cost < slot_num and remain_kiss > 0:
				remain_kiss -= 1
				best_plan[i].append(kiss_gem)
				# Extra score induced by Kiss gem
				kiss_score = stats['gem_score'][kiss_gem]
				# If the card has Trick gem, the Kiss gem will have extra score
				if any(['Trick' in gem for gem in best_plan[i]]):
					CR = 1 - (1-np.array([x['stats']['CR'] for x in team_info])).prod()
					print(kiss_score, CR, math.ceil(0.33*CR*stats['gem_score'][kiss_gem]/(1+stats['cskill_bonus']/100)))
					kiss_score += math.ceil(0.33*CR*stats['gem_score'][kiss_gem]/(1+stats['cskill_bonus']/100))
				best_score_list[i] += kiss_score
				Qmax += kiss_score

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
	def build_team_fix_cskill(self, cskill, K, method, alloc_method):
		def single_case(choice, center, candidates, max_score=0):
			# Assemble a new team
			team_info = ([center] + [candidates[i] for i in choice]).copy()
			# Update score of gems
			team_info, team_base_score, best_gem_score, CR = self.update_gem_score(team_info, sort=alloc_method=='DC')
			# # If for unlimited gem the choice is worse than max_score, drop it
			if team_base_score + best_gem_score < max_score: return None
			# Solve for best gem allocation
			if alloc_method == 'DP':
				alloc_info, alloc_score = self.find_optimal_gem_allocation_DP(team_info)
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
		
		center, candidates = self.find_candidates(cskill, K, no_kiss=alloc_method=='DP')
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
			score_map, eliminate = defaultdict(lambda:0), defaultdict(lambda:False)
			# Initialize queue
			choice = tuple(list(range(8)))
			team_info, alloc_info, total_score, CR = single_case(choice, center, candidates)
			score_map[choice] = total_score
			max_score, best_team = total_score, construct_team(team_info, alloc_info, CR)
			queue = [choice]

			while len(queue) > 0:
				choice = queue.pop(0)
				eliminate[choice] = True
				rest = [x for x in range(K) if x not in choice]
				for tt in range(1,t+1):
					for pos in itertools.combinations(list(range(8)), tt):
						neighbor = list(choice)
						for new_idx in itertools.combinations(rest, tt):
							for i in range(tt): neighbor[pos[i]] = new_idx[i]
							new_choice = tuple(sorted(neighbor))
							# If this team combination has not been computed, compute it
							if score_map[new_choice] == 0:
								res = single_case(new_choice, center, candidates, score_map[choice])
								if res is None: 
									score_map[new_choice] = 1
									continue
								team_info, alloc_info, total_score, CR = res
								score_map[new_choice] = total_score
								if total_score > max_score:
									max_score, best_team = total_score, construct_team(team_info, alloc_info, CR)
							# If the new choice is better, add it to the queue to examine later
							# otherwise the new choice is not promising, eliminate it
							if not eliminate[new_choice] and score_map[new_choice] >= score_map[choice]:
								queue.append(new_choice)
							else:
								eliminate[new_choice] = True
		else:
			print('Unrecognized method {0}, only support brute and t-suboptimal'.format(method))
			raise		
		return max_score, best_team
	def build_team(self, K=15, method='4-suboptimal', alloc_method='DP'):
		def construct_gem_dicts():
			attr2_list = ['Princess', 'Angel', 'Empress']
			attr, attr2 = self.live.attr, attr2_list[attr_list.index(self.live.attr)]
			gem_list  = [attr+' Perfume']
			gem_list += [attr+x+grade for x in [' Ring ', ' Cross '] for grade in ['(1st)', '(2nd)', '(3rd)']]
			gem_list += [attr+x for x in [' Aura', ' Veil']]
			gem_list += [attr2+x for x in [' Charm', ' Heal'] for attr2 in attr2_list] + [attr2+' Trick']
			self.gem_dict = {k:v for k,v in enumerate(gem_list)}
			self.gem_rev_dict = {v:k for k,v in enumerate(gem_list)}
			self.gem_occupy = [self.owned_gem[gem] for gem in gem_list]
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

		print('Team searching method: {0}. Gem allocation searching method: {1}'.format(method, alloc_method))
		if alloc_method == 'DP': construct_gem_dicts()
		cskill_list, result = find_candidate_cskill(), []
		max_score, best_team = 0, None
		for i, cskill in enumerate(cskill_list,1):
			score, team = self.build_team_fix_cskill(cskill=cskill, K=K, method=method, alloc_method=alloc_method)
			result.append((score, team))
			print('{0}/{1}: Best team has score {2:6d} for {3}'.format(i, len(cskill_list), score, cskill))
			if score > max_score: max_score, best_team = score, team

		self.best_team = best_team
		# self.best_team = result[-1][1]
		return self.show_best_team_stats()

	def show_best_team_stats(self, show_cost=False):
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
					 	if self.live.attr in gem.name and gem.effect == 'team_boost']
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
					'Gem':gem_slot_pic(card, show_cost=show_cost, gem_size=25-5*show_cost)}

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