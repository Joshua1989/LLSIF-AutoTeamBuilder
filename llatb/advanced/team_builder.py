import numpy as np
import pandas as pd
from collections import defaultdict
from random import shuffle
import math, itertools, copy, time
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
		self.log = ''

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
			self.log += 'Did not find center card with index {0}\n'.format(center_idx)
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

	def find_candidates(self, cskill, K, pin_index=[], exclude_index=[]):
		# Compute rough strength
		for card in self.cards:
			card.compute_rough_strength(cskill, self.guest_cskill, self.live, self.setting)
		self.cards.sort(key=lambda x: x.rough_strength[self.live.attr]['strength'], reverse=True)
		# Find the best card and choose it to be the center, and find K best cards from the rest for candidates
		center, candidates, pinned = None, [], []
		k, k_pin, CC = 0, 0, CoverageCalculator(self.live, self.setting)
		for card in self.cards:
			if card.index in exclude_index: continue
			if card.has_same_cskill and center is None:
				card.compute_card_stats(cskill, self.guest_cskill, self.live, self.setting)
				if card.CR is None: card.CR, card.CR_list = CC.compute_coverage(card)
				if card.index in pin_index: k_pin += 1
				center = card
			elif k < K and card.index not in pin_index:
				card.compute_card_stats(cskill, self.guest_cskill, self.live, self.setting)
				if card.CR is None: card.CR, card.CR_list = CC.compute_coverage(card)
				candidates.append(card)
				k += 1
			elif card.index in pin_index:
				card.compute_card_stats(cskill, self.guest_cskill, self.live, self.setting)
				if card.CR is None: card.CR, card.CR_list = CC.compute_coverage(card)
				k_pin += 1
				pinned.append(card)
			if center is not None and k >= K and k_pin == len(pin_index): break
		if center is None:
			print('There is no card has center skill', cskill)
			self.log += 'There is no card has center skill {0}\n'.format(cskill)
			raise
		return center, candidates, pinned

	def build_team_fix_cskill(self, cskill, K, method, alloc_method, pin_index=[], exclude_index=[]):
		def single_case(choice, center, candidates, pinned, max_score=0):
			gem_allocator = GemAllocator([center] + pinned + [candidates[i] for i in choice], self.live, self.setting, self.owned_gem)
			res = gem_allocator.allocate(alloc_method, max_score)
			return gem_allocator if res is not None else None

		center, candidates, pinned = self.find_candidates(cskill, K, pin_index, exclude_index)
		if method == 'brute':
			best_gem_allocator = single_case(tuple(list(range(8-len(pinned)))), center, candidates, pinned, 0)
			for choice in itertools.combinations(list(range(K)), 8-len(pinned)):
				gem_allocator = single_case(choice, center, candidates, pinned, best_gem_allocator.total_score)
				if gem_allocator is None: continue
				if gem_allocator.total_score > best_gem_allocator.total_score:
					best_gem_allocator = gem_allocator
		elif '-suboptimal' in method:
			t = int(method.replace('-suboptimal', ''))
			if t not in list(range(1,9)): 
				print('Suboptimal step must be in {1,...,8}')
				self.log += 'Suboptimal step must be in {1,...,8}\n'
				raise

			# Use a map to keep track of computed team to avoid duplicated computation
			score_map, eliminate = defaultdict(lambda:0), defaultdict(lambda:False)
			# Initialize queue
			choice = tuple(list(range(8-len(pinned))))
			gem_allocator = single_case(choice, center, candidates, pinned)
			best_gem_allocator = gem_allocator
			score_map[choice] = gem_allocator.total_score
			queue = [choice]

			while len(queue) > 0:
				choice = queue.pop(0)
				eliminate[choice] = True
				rest = [x for x in range(K) if x not in choice]
				for tt in range(1,t+1):
					for pos in itertools.combinations(list(range(8-len(pinned))), tt):
						neighbor = list(choice)
						for new_idx in itertools.combinations(rest, tt):
							for i in range(tt): neighbor[pos[i]] = new_idx[i]
							new_choice = tuple(sorted(neighbor))
							# If this team combination has not been computed, compute it
							if score_map[new_choice] == 0:
								gem_allocator = single_case(new_choice, center, candidates, pinned, best_gem_allocator.total_score)
								if gem_allocator is None: 
									score_map[new_choice] = 1
									continue
								score_map[new_choice] = gem_allocator.total_score
								if gem_allocator.total_score > best_gem_allocator.total_score:
									best_gem_allocator = gem_allocator
							# If the new choice is better, add it to the queue to examine later
							# otherwise the new choice is not promising, eliminate it
							if not eliminate[new_choice] and score_map[new_choice] >= score_map[choice]:
								queue.append(new_choice)
							else:
								eliminate[new_choice] = True
		else:
			print('Unrecognized method {0}, only support brute and t-suboptimal'.format(method))
			self.log += 'Unrecognized method {0}, only support brute and t-suboptimal\n'.format(method)
			raise		
		return best_gem_allocator

	def build_team(self, K=15, method='4-suboptimal', alloc_method='DC', show_cost=False, time_limit=24, pin_index=[], exclude_index=[]):
		def find_candidate_cskill():
			# Enumerate center skill of the highest rarity card that have same attribute with live
			rarity_list = ['UR','SSR','SR','R']
			cskill_dict = {rarity:[] for rarity in rarity_list}
			is_new = lambda rarity, cskill: all([not x.is_equal(cskill) for x in cskill_dict[rarity]])
			for card in self.cards:
				if card.index in exclude_index: continue
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
			shuffle(candidate_cskill)
			return candidate_cskill

		start_time = time.time()
		print('{2} {3}: Team searching method: {0}. Gem allocation searching method: {1}'.format(method, alloc_method, self.live.name, self.live.difficulty))
		self.log += 'Team searching method: {0}. Gem allocation searching method: {1}\n'.format(method, alloc_method)
		cskill_list, result = find_candidate_cskill(), []
		max_score, best_team = 0, None
		opt = {'score_up_bonus':self.score_up_bonus, 'skill_up_bonus':self.skill_up_bonus, 'guest_cskill':self.guest_cskill}
		for i, cskill in enumerate(cskill_list,1):
			try:
				gem_allocator = self.build_team_fix_cskill(cskill=cskill, K=K, method=method, alloc_method=alloc_method, pin_index=pin_index, exclude_index=exclude_index)
				exp_score = gem_allocator.construct_team().compute_expected_total_score(self.live, opt=opt)
				result.append((exp_score, gem_allocator))
			except:
				exp_score = -1
			elapsed_time = time.time() - start_time
			print('{0}/{1}: {4:5.2f} secs elapsed, best team has score {2:6d} for {3}'.format(i, len(cskill_list), exp_score, cskill, elapsed_time))
			self.log += '{0}/{1}: Best team has score {2:6d} for {3}\n'.format(i, len(cskill_list), exp_score, cskill)
			if exp_score > max_score: max_score, best_gem_allocator = exp_score, gem_allocator
			if elapsed_time > time_limit:
				print('Due to HTTP response time limit, jump out of the algorithm')
				break

		self.best_gem_allocator = best_gem_allocator
		self.best_team = best_gem_allocator.construct_team()
		return self.view_result(), (i, len(cskill_list))

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

	def view_result(self, show_cost=False, lang='EN', fixed_team=None):
		try:
			return self.best_gem_allocator.view_optimal_details(show_cost=show_cost, lang=lang, fixed_team=fixed_team)
		except:
			print('The best team has not been formed yet')

	def team_alloc(self, team, alloc_method='DC', show_cost=False):
		candidates, CC = [], CoverageCalculator(self.live, self.setting)
		for index, card in enumerate(team.card_list):
			adv_card = AdvancedCard(index, card)
			adv_card.list_gem_allocation(self.live)
			adv_card.compute_card_stats(team.center().cskill, self.guest_cskill, self.live, self.setting)
			adv_card.CR, adv_card.CR_list = CC.compute_coverage(card)
			if index == 4:
				center = adv_card
			else:
				candidates.append(adv_card)
		gem_allocator = GemAllocator([center] + candidates, self.live, self.setting, self.owned_gem)
		gem_allocator.allocate(alloc_method)
		return gem_allocator.view_optimal_details(show_cost=show_cost)

	def team_strength_detail(self, team, show_cost=False):
		candidates, CC = [], CoverageCalculator(self.live, self.setting)
		for index, card in enumerate(team.card_list):
			adv_card = AdvancedCard(index, card)
			adv_card.list_gem_allocation(self.live)
			adv_card.compute_card_stats(team.center().cskill, self.guest_cskill, self.live, self.setting)
			adv_card.CR, adv_card.CR_list = CC.compute_coverage(card)
			if index == 4:
				center = adv_card
			else:
				candidates.append(adv_card)
		gem_allocator = GemAllocator([center] + candidates, self.live, self.setting, self.owned_gem)
		gem_allocator.update_gem_score()
		new_team = Team(candidates[:4]+[center]+candidates[4:])
		return gem_allocator.view_optimal_details(show_cost=show_cost, fixed_team=new_team)