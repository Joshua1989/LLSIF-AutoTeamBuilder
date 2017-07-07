import numpy as np
import pandas as pd
from collections import defaultdict
import math, itertools, copy
from llatb.common.global_var import *
from llatb.framework import card_dataframe, Team
from llatb.framework.live import Live, DefaultLive
from llatb.common.display import gem_slot_pic, view_cards
from llatb.common.config import misc_path, icon_path, gem_path
from llatb.simulator import Simulator
from IPython.display import HTML
from llatb.advanced.gem_allocator import GemAllocator, AdvancedCard
from llatb.advanced.judge_coverage import CoverageCalculator



class TeamBuilder:
	def __init__(self, live, game_data, opt={}):
		self.owned_gem = copy.deepcopy(game_data.owned_gem)
		self.live = live
		self.guest_cskill = opt.get('guest_cskill',None)
		self.score_up_bonus = opt.get('score_up_bonus',0)
		self.skill_up_bonus = opt.get('skill_up_bonus',0)
		self.generate_setting(opt)
		self.cards = [AdvancedCard(index, card) for index, card in game_data.raw_card.items()]
		for card in self.cards: card.list_gem_allocation(self.live)
		self.best_team = None

	def generate_setting(self, opt={}):
		res = { key:getattr(self.live, key) for key in ['note_number', 'duration', 'star_density', 'note_type_dist', 'perfect_rate'] }
		res['attr_group_factor'] = 1
		res['team_strength'] = opt.get('rough_team_strength', 80000)
		res['guest_cskill']  = self.guest_cskill
		res['score_up_rate'] = 1 + self.score_up_bonus
		res['skill_up_rate'] = 1 + self.skill_up_bonus
		self.setting = res

	def show_rough_strength(self, center_idx, head=None):
		keys = [ 'index', 'card_id', 'member_name', 'main_attr',
				 'idolized', 'promo', 'rarity',
				 'level', 'max_level', 
				 'bond', 'max_bond', 
				 'hp', 'smile', 'pure', 'cool',
				 'skill', 'cskill', 
				 'slot_num', 'max_slot_num', 'equipped_gems', 'tags']
		columns  = keys + ['Same CSkill']
		columns += ['Rough '+attr for attr in attr_list] + ['Use Gem '+attr for attr in attr_list]
		center_card, data = None, []

		for card in self.cards:
			if card.index == center_idx:
				center_card = card
				break
		if center_card is None:
			print('Did not find center card with index', center_idx)
			raise
		for card in self.cards:
			res = {k:getattr(card,k) for k in keys}
			card.compute_rough_strength(center_card.cskill, self.guest_cskill, self.live, self.setting)
			for attr in attr_list:
				res['Rough '+attr] = card.rough_strength[attr]['strength']
				res['Use Gem '+attr] = card.rough_strength[attr]['use_skill_gem']
			res['Same CSkill'] = card.has_same_cskill
			data.append(res)
		data.sort(key=lambda x: x['Rough '+self.live.attr], reverse=True)

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

	def find_candidates(self, cskill, K):
		# Compute rough strength
		for card in self.cards:
			card.compute_rough_strength(cskill, self.guest_cskill, self.live, self.setting)
		self.cards.sort(key=lambda x: x.rough_strength[self.live.attr]['strength'], reverse=True)
		# Find the best card and choose it to be the center, and find K best cards from the rest for candidates
		center, candidates, k, CC = None, [], 0, CoverageCalculator(self.live)
		for card in self.cards:
			if card.has_same_cskill and center is None:
				card.compute_card_stats(cskill, self.guest_cskill, self.live, self.setting)
				card.CR = CC.compute_coverage(card)
				center = card
			elif k < K:
				card.compute_card_stats(cskill, self.guest_cskill, self.live, self.setting)
				card.CR = CC.compute_coverage(card)
				candidates.append(card)
				k += 1
			if center is not None and k >= K: break
		if center is None:
			print('There is no card has center skill', cskill)
			raise
		return center, candidates

	def build_team_fix_cskill(self, cskill, K, method, alloc_method):
		def single_case(choice, center, candidates, max_score=0):
			gem_allocator = GemAllocator([center] + [candidates[i] for i in choice], self.live, self.setting, self.owned_gem)
			res = gem_allocator.allocate(alloc_method, max_score)
			return gem_allocator if res is not None else None

		center, candidates = self.find_candidates(cskill, K)
		if method == 'brute':
			max_score, best_team = 0, None
			for choice in itertools.combinations(list(range(K)), 8):
				gem_allocator = single_case(choice, center, candidates, max_score)
				if gem_allocator is None: continue
				if gem_allocator.total_score > max_score:
					max_score, best_team = gem_allocator.total_score, gem_allocator.construct_team()
		elif '-suboptimal' in method:
			t = int(method.replace('-suboptimal', ''))
			if t not in list(range(1,9)): 
				print('Suboptimal step must be in {1,...,8}')
				raise

			max_score, best_team = 0, None
			# Use a map to keep track of computed team to avoid duplicated computation
			score_map, eliminate = defaultdict(lambda:0), defaultdict(lambda:False)
			# Initialize queue
			choice = tuple(list(range(8)))
			gem_allocator = single_case(choice, center, candidates)
			score_map[choice] = gem_allocator.total_score
			max_score, best_team = gem_allocator.total_score, gem_allocator.construct_team()
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
								gem_allocator = single_case(new_choice, center, candidates, max_score)
								if gem_allocator is None: 
									score_map[new_choice] = 1
									continue
								score_map[new_choice] = gem_allocator.total_score
								if gem_allocator.total_score > max_score:
									max_score, best_team = gem_allocator.total_score, gem_allocator.construct_team()
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

	def build_team(self, K=15, method='4-suboptimal', alloc_method='DC', show_cost=False):
		def find_candidate_cskill():
			# Enumerate center skill of the highest rarity card that have same attribute with live
			rarity_list = ['UR','SSR','SR','R']
			cskill_dict = {rarity:[] for rarity in rarity_list}
			is_new = lambda rarity, cskill: all([not x.is_equal(cskill) for x in cskill_dict[rarity]])
			for card in self.cards:
				if card.main_attr != self.live.attr or card.rarity not in rarity_list: continue
				rarity, cskill = 'R' if card.promo else card.rarity, card.cskill
				if is_new(rarity, cskill): 
					cskill_dict[rarity].append(cskill)
			candidate_cskill = [None]
			for rarity in rarity_list:
				if len(cskill_dict[rarity]) > 0:
					candidate_cskill = cskill_dict[rarity]
					break
			candidate_cskill.sort(key=lambda x: str(x))
			return candidate_cskill

		print('Team searching method: {0}. Gem allocation searching method: {1}'.format(method, alloc_method))
		cskill_list, result = find_candidate_cskill(), []
		max_score, best_team = 0, None
		opt = {'score_up_bonus':self.score_up_bonus, 'skill_up_bonus':self.skill_up_bonus, 'guest_cskill':self.guest_cskill}
		for i, cskill in enumerate(cskill_list,1):
			score, team = self.build_team_fix_cskill(cskill=cskill, K=K, method=method, alloc_method=alloc_method)
			exp_score = team.compute_expected_total_score(self.live, opt=opt)
			result.append((exp_score, team))
			print('{0}/{1}: Best team has score {2:6d} for {3}'.format(i, len(cskill_list), score, cskill))
			if exp_score > max_score: max_score, best_team = exp_score, team

		self.best_team = best_team
		return self.team_alloc(best_team, alloc_method=alloc_method, show_cost=show_cost)

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

	def team_alloc(self, team, alloc_method='DC', show_cost=False):
		candidates, CC = [], CoverageCalculator(self.live)
		for index, card in enumerate(team.card_list):
			adv_card = AdvancedCard(index, card)
			adv_card.list_gem_allocation(self.live)
			adv_card.compute_card_stats(team.center().cskill, self.guest_cskill, self.live, self.setting)
			adv_card.CR = CC.compute_coverage(card)
			if index == 4:
				center = adv_card
			else:
				candidates.append(adv_card)
		gem_allocator = GemAllocator([center] + candidates, self.live, self.setting, self.owned_gem)
		gem_allocator.allocate(alloc_method)
		new_team = gem_allocator.construct_team()
		# new_team.compute_expected_total_score(self.live, opt=self.setting, verbose=True)
		# new_team.to_LLHelper('team.sd')
		# new_team.to_ieb('team.ieb')
		return gem_allocator.view_optimal_details(show_cost=show_cost)