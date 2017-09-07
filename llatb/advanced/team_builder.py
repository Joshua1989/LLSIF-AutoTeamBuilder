import numpy as np
import pandas as pd
from collections import defaultdict
from random import shuffle
import math, itertools, copy, time
from llatb.common.global_var import *
from llatb.framework import card_dataframe, Team
from llatb.framework.live import Live, DefaultLive
from llatb.common.display import gem_slot_pic, view_cards
from llatb.common.config import misc_path, icon_path, gem_path, html_template
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

	def show_rough_strength(self, extra_col=[], no_skill=True):
		def get_summary(card, ext_col=[]):
			res = {'index':int(card.index)}
			match_cskill = self.guest_cskill is not None and self.guest_cskill.bonus_range in card.tags
			match_color, match_group = card.main_attr == self.live.attr, self.live.group in card.tags
			font_color, font_weight = attr_color[self.live.attr] if match_color else 'black', 900 if match_cskill else 'normal'
			border_style = '3px double' if (match_color and match_group) else ('1px solid' if (match_color or match_group) else '1px none')
			res['CID'] = '<span style="color:{1}; border:{1} {2};font-weight:{3}; padding: 0 3px">{0}</span>'.format(card.card_id, font_color, border_style, font_weight)
			# Generate HTML code for card view and skill
			res[col_name['view']] =  '<img src="{0}" width=50 title="{1}"/>'.format(icon_path(card.card_id, card.idolized), card.tooltip())

			if card.skill is not None:
				temp = repr(card.skill).split(': ')
				fmt = '<p> <img style="float: left" src="{0}" width=15 /> {1} <br style="clear: both;"/> {2} <br/> {3} </p>'
				res[col_name['skill']] = fmt.format(misc_path(card.skill.effect_type) ,temp[0], *temp[1].split('. '))
			else:
				res[col_name['skill']] = '<p>{0}</p>'.format('NA')
			if card.cskill is not None:
				temp = repr(card.cskill).split('. ')
				func = lambda x: x.split(': ')[-1].replace('raise', 'Raise').replace('contribution ','')
				if temp[1] == '':
					res[col_name['skill']] += '<p>{0}</p>'.format(func(temp[0]))
				else:
					res[col_name['skill']] += '<p>{0}<br/>{1}</p>'.format(func(temp[0]), func(temp[1]))

			fmt = '<p style="color:{0};">{1}<br/>{2}</p>'
			res[col_name['level']] = fmt.format('black', card.level, card.max_level)
			res[col_name['bond']] = fmt.format('black', card.bond, card.max_bond)
			res[col_name['hp']] = '<p style="color:orange;"><b>{0}</b></p>'.format(card.hp)
			res['Slot'] = card.slot_num

			fmt = '<p style="color:{0};">{1}<br>{2}</p>'
			card.compute_rough_strength(cskill=None, guest_cskill=self.guest_cskill, live=self.live, setting=self.setting)
			roungh_str_fmt = lambda attr: ('<b style="border:1px solid; padding:0px 1px">{0}</b>' if card.rough_strength[attr]['use_skill_gem'] else '{0}').format(card.rough_strength[attr]['strength'])
			for attr in attr_list:
				res[col_name[attr.lower()]] = fmt.format(attr_color[attr], getattr(card, attr.lower()), roungh_str_fmt(attr))
			res['sort_STR'] = card.rough_strength[self.live.attr]['strength']

			if card.skill is None:
				res['skill_effect_type'] = 'NA'
				res['skill_gain'] = 0
				res['Skill Gain'] = '<p>NA</p>'
			else:
				gain = card.skill.skill_gain(self.setting)[0]
				res['skill_effect_type'] = card.skill.effect_type
				res['skill_gain'] = gain
				if card.skill.effect_type in ['Strong Judge', 'Weak Judge']:
					res['Skill Gain'] = '<p><img style="float: left" src="{2}" width=15 />Lv:{1}<br clear="both"/>{0:.2f}%<br/>covered</p>'.format(100*gain, card.skill.level, misc_path(card.skill.effect_type))
				elif card.skill.effect_type == 'Stamina Restore':
					res['Skill Gain'] = '<p><img style="float: left" src="{2}" width=15 />Lv:{1}<br clear="both"/>{0:.4f}<br/>hp/note</p>'.format(gain, card.skill.level, misc_path(card.skill.effect_type))
				elif card.skill.effect_type == 'Score Up':
					res['Skill Gain'] = '<p><img style="float: left" src="{2}" width=15 />Lv:{1}<br clear="both"/>{0:.4f}<br/>pt/note</p>'.format(gain, card.skill.level, misc_path(card.skill.effect_type))

			# If there are other columns to show
			for attr in ext_col: res[attr] = getattr(card, attr)
			return res

		col_name = {'view':'<p><b> Card View </b></p>', 'skill':'<p><b> Skill & Center Skill </b></p>'}
		col_name.update({ x:'<img src="{0}" width=25/>'.format(misc_path(x)) for x in ['level','bond','hp','smile','pure','cool'] })
		columns  = ['index', 'CID']
		columns += [col_name[x] for x in ['view', 'skill', 'level', 'bond', 'hp', 'smile', 'pure', 'cool']]
		columns += ['Slot', 'Skill Gain'] + ['sort_STR', 'skill_effect_type', 'skill_gain'] + extra_col

		data = [get_summary(card, ext_col=extra_col) for card in self.cards if card.rarity not in ['N', 'R']]
		df = pd.DataFrame(data, columns=columns)
		df = df.set_index('index')
		df.index.name = ''

		df_all = df.sort_values(by='sort_STR', ascending=False)
		del df_all['sort_STR']
		del df_all['skill_effect_type']
		del df_all['skill_gain']
		if no_skill:
			del df_all['<p><b> Skill & Center Skill </b></p>']
			del df_all[col_name['hp']]

		df_healer = df[df.skill_effect_type=='Stamina Restore'].sort_values(by='skill_gain', ascending=False)
		del df_healer['sort_STR']
		del df_healer['skill_effect_type']
		del df_healer['skill_gain']
		if no_skill:
			del df_healer['<p><b> Skill & Center Skill </b></p>']
			del df_healer[col_name['hp']]

		df_plocker = df[df.apply(lambda x: 'Judge' in x.skill_effect_type, axis=1)].sort_values(by='skill_gain', ascending=False)
		del df_plocker['sort_STR']
		del df_plocker['skill_effect_type']
		del df_plocker['skill_gain']
		if no_skill:
			del df_plocker['<p><b> Skill & Center Skill </b></p>']
			del df_plocker[col_name['hp']]
		return {'all': HTML(html_template.format(df_all.to_html(escape=False))),
				'healer': HTML(html_template.format(df_healer.to_html(escape=False))),
				'plocker': HTML(html_template.format(df_plocker.to_html(escape=False)))}

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

	def build_team(self, K=15, method='4-suboptimal', alloc_method='DC', show_cost=False, time_limit=24, 
		pin_index=[], exclude_index=[], next_cskill_index=0, prev_max_cskill_index=0):
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
			# shuffle(candidate_cskill)
			return candidate_cskill

		start_time = time.time()
		print('{2} {3}: Team searching method: {0}. Gem allocation searching method: {1}'.format(method, alloc_method, self.live.name, self.live.difficulty))
		self.log += 'Team searching method: {0}. Gem allocation searching method: {1}\n'.format(method, alloc_method)
		cskill_list, result = find_candidate_cskill(), []
		max_score, best_team, max_cskill_index = 0, None, 0
		opt = {'score_up_bonus':self.score_up_bonus, 'skill_up_bonus':self.skill_up_bonus, 'guest_cskill':self.guest_cskill}
		for i, cskill in enumerate(cskill_list,1):
			if i != prev_max_cskill_index and i < next_cskill_index: continue
			try:
				gem_allocator = self.build_team_fix_cskill(cskill=cskill, K=K, method=method, alloc_method=alloc_method, pin_index=pin_index, exclude_index=exclude_index)
				exp_score = gem_allocator.construct_team().compute_expected_total_score(self.live, opt=opt)
				result.append((exp_score, gem_allocator))
			except:
				exp_score = -1
			elapsed_time = time.time() - start_time
			print('{0}/{1}: {4:5.2f} secs elapsed, best team has score {2:6d} for {3}'.format(i, len(cskill_list), exp_score, cskill, elapsed_time))
			self.log += '{0}/{1}: Best team has score {2:6d} for {3}\n'.format(i, len(cskill_list), exp_score, cskill)
			if exp_score > max_score: max_score, best_gem_allocator, max_cskill_index = exp_score, gem_allocator, i
			if elapsed_time > time_limit and i < len(cskill_list):
				print('Due to HTTP response time limit, jump out of the algorithm')
				break

		self.best_gem_allocator = best_gem_allocator
		self.best_team = best_gem_allocator.construct_team()
		print('{0} out of {1} cases computed, index of best cskill is {2}'.format(i, len(cskill_list), max_cskill_index))
		return self.best_team, (i, len(cskill_list), max_cskill_index)

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