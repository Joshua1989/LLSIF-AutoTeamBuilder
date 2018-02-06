import numpy as np
import pandas as pd
from math import ceil
from llatb.common.global_var import *
from llatb.framework import Card

# Class for a single card gem allocation, only contains the gem allocation and its score
class Alloc:
	def __init__(self, gems, score=0):
		self.gems = gems
		self.score = score
	def __repr__(self):
		return str((self.gems, self.score))

class AdvancedCard(Card):
	def __init__(self, index, card):
		self.index = int(index)
		args = [getattr(card, x) for x in ['card_id', 'card_name', 'member_name', 'rarity', 'main_attr', 'stats_list', 'idolized', 'skill', 'cskill', 'promo']]
		Card.__init__(self, *args)
		self.level_up(slot_num=card.slot_num, level=card.level, bond=card.bond)
		self.equip_gem([x.name for x in card.equipped_gems])

		self.attr2 = attr2_list[attr_list.index(self.main_attr)]
		temp = [int(tag[0]) for tag in self.tags if '-year' in tag]
		self.grade = '' if len(temp) == 0 else {1:'(1st)', 2:'(2nd)', 3:'(3rd)'}[int(temp[0])]
		self.is_charm = self.skill is not None and self.skill.effect_type == 'Score Up' and self.slot_num >= 4
		self.is_heal = self.skill is not None and self.skill.effect_type == 'Stamina Restore' and self.slot_num >= 4
		self.is_trick = self.skill is not None and self.skill.effect_type in ['Weak Judge', 'Strong Judge'] and self.slot_num >= 4
		self.CR, self.CR_list = None, None
	def compute_rough_strength(self, cskill, guest_cskill, live, setting):
		# Compute rough strength and sort them by live attribute
		setting = setting.copy()
		setting.update({'cskill1':cskill, 'cskill2':guest_cskill, 'group_match':live.group in self.tags})
		self.rough_strength = self.general_strength(setting=setting)
		self.has_same_cskill = False if self.cskill is None else self.cskill.is_equal(cskill)
	def list_gem_allocation(self, live):
		def unique(l):
			result, aux = list(), list()
			for x in l:
				if set(x) not in aux:
					result.append(x)
					aux.append(set(x))
			return result
		# Find all possible gem allocation
		gem_alloc = {0:[[]], 1:[[live.attr+' Kiss']], 2:[[live.attr+' Perfume'], [live.attr+' Ring '+self.grade]], 
					 3:[[live.attr+' Cross '+self.grade], [live.attr+' Aura']], 4:[[live.attr+' Veil']], 5:[], 6:[], 7:[], 8:[]}
		if live.attr == self.main_attr:
			gem_alloc[4].append([self.attr2+' Trick'])
		if self.is_charm:
			gem_alloc[4].append([self.attr2+' Charm'])
		elif self.is_heal:
			gem_alloc[4].append([self.attr2+' Heal'])

		for i in range(3,self.slot_num+1):
			temp = []
			for j in range(ceil(i/2),i):
				alloc1, alloc2 = gem_alloc[j], gem_alloc[i-j]
				for item1 in alloc1:
					for item2 in alloc2:
						if set(item1)&set(item2) == set():
							temp.append(list(set(item1)|set(item2)))
			gem_alloc[i] += unique(temp)
		self.gem_alloc_list = [ Alloc(gems, 0) for k,v in gem_alloc.items() for gems in v if k <= self.slot_num ]
	def compute_card_stats(self, cskill, guest_cskill, live, setting):
		# Compute same group & same color bonus
		self.mu = attr_match_factor**(live.attr==self.main_attr) * group_match_factor**(live.group in self.tags)
		# Compute the single card judge cover rate
		# self.CR = 0 if not self.is_trick else self.skill.skill_gain(setting=setting)[0]
		# Compute center skill bonus and card base score before same group & same color bonus
		self.base_bond_value = getattr(self, live.attr.lower()) + self.bond * (self.main_attr==live.attr) 
		self.cskill_bonus, self.base_stat = 0, 0
		if cskill is not None:
			if cskill.main_attr == live.attr:
				if cskill.base_attr == live.attr:
					self.cskill_bonus += cskill.main_ratio/100
				else:
					self.base_stat += ceil( (getattr(self,cskill.base_attr.lower()) + self.bond*(self.main_attr==cskill.base_attr) )*cskill.main_ratio/100)
				if cskill.bonus_ratio is not None:
					self.cskill_bonus += (cskill.bonus_range in self.tags) * cskill.bonus_ratio/100
		if guest_cskill is not None: 
			if guest_cskill.main_attr == live.attr:
				if guest_cskill.base_attr == live.attr:
					self.cskill_bonus += guest_cskill.main_ratio/100
				else:
					self.base_stat += ceil( (getattr(self,guest_cskill.base_attr.lower()) + self.bond*(self.main_attr==guest_cskill.base_attr) )*guest_cskill.main_ratio/100)
				if guest_cskill.bonus_ratio is not None:
					self.cskill_bonus += (guest_cskill.bonus_range in self.tags) * guest_cskill.bonus_ratio/100
		self.base_stat += ceil(self.base_bond_value*(1+self.cskill_bonus))
		# For skills that are not Score or Perfect or Star Perfect triggered, we do not need to compute it again
		if self.skill is not None and self.skill.effect_type in ['Score Up', 'Stamina Restore'] and self.skill.trigger_type not in ['Score', 'Perfect', 'Star']:
			self.skill_gain = self.skill.skill_gain(setting=setting)[0]
	def update_gem_score(self, mu_bar, team_CR, team_total_stat, live, new_setting, sort=False):
		# Compute the score of each gem
		boost = live.pts_per_strength * mu_bar * new_setting['score_up_rate']
		self.card_base_score = ceil(self.base_stat*boost)
		if self.skill is not None and self.skill.effect_type == 'Score Up':
			# If the skill is Score/Perfect/Star triggered, compute the skill gain under new settings
			if self.skill.trigger_type in ['Score', 'Perfect', 'Star']:
				self.skill_gain = self.skill.skill_gain(setting=new_setting)[0]
			self.card_base_score += ceil(self.skill_gain*live.note_number)

		# Compute the score for each kind of gem
		gem_score = dict()
		if self.slot_num >= 1:
			gem_score[live.attr +' Kiss'] = ceil(ceil(200 * (1+self.cskill_bonus)) * boost)
		if self.slot_num >= 2:
			gem_score[live.attr +' Perfume'] = ceil(ceil(450 * (1+self.cskill_bonus)) * boost)
			gem_score[live.attr +' Ring '+ self.grade] = ceil(ceil(ceil(self.base_bond_value*0.1) * (1+self.cskill_bonus)) * boost)
		if self.slot_num >= 3:
			gem_score[live.attr +' Cross '+ self.grade] = ceil(ceil(ceil(self.base_bond_value*0.16) * (1+self.cskill_bonus)) * boost)
			gem_score[live.attr +' Aura'] = ceil(team_total_stat * 0.018 * boost)
		if self.slot_num >= 4:
			gem_score[live.attr +' Veil'] = ceil(team_total_stat * 0.024 * boost)
			if live.attr == self.main_attr:
				gem_score[self.attr2+' Trick'] = ceil(0.33 * team_CR * self.base_bond_value * boost)
			if self.is_charm:
				# If the skill is Score/Perfect/Star triggered, compute the skill gain under new settings
				if self.skill.trigger_type in ['Score', 'Perfect', 'Star']:
					self.skill_gain = self.skill.skill_gain(setting=new_setting)[0]
				gem_score[self.attr2+' Charm'] = ceil(1.5 * self.skill_gain * live.note_number)
			if self.is_heal:
				# If the skill is Score/Perfect/Star triggered, compute the skill gain under new settings
				if self.skill.trigger_type in ['Score', 'Perfect', 'Star']:
					self.skill_gain = self.skill.skill_gain(setting=new_setting)[0]
				gem_score[self.attr2+' Heal'] = ceil(480 * self.skill_gain * live.note_number)
		self.gem_score = gem_score
		# Compute the score for all possible gem allocation for this card
		self.max_alloc_score = 0
		for alloc in self.gem_alloc_list:
			alloc.score = 0
			# If allocation does not contain Trick gem, simply sum them up
			# If allocation contains Trick gem, add extra point from single card gems
			for gem in alloc.gems: 
				alloc.score += self.gem_score[gem]
			if self.attr2+' Trick' in alloc.gems:
				for gem in alloc.gems: 
					if gem.split()[1] in ['Kiss', 'Perfume', 'Ring', 'Cross']:
						alloc.score += ceil(0.33 * team_CR * self.gem_score[gem] / (1+self.cskill_bonus))
			if alloc.score > self.max_alloc_score:
				self.max_alloc_score = alloc.score
		# Sort all possible allocation by score
		if sort: self.gem_alloc_list.sort(key=lambda x: x.score, reverse=True)