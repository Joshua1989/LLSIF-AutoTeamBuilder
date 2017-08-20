import numpy as np
import pandas as pd
from copy import deepcopy
from llatb.skill import Skill, CenterSkill, GemSkill
from llatb.common.global_var import *

class Card:
	def __init__(self, card_id, card_name, member_name, rarity, main_attr, stats_list, idolized, skill, cskill, promo=False):
		if not all([card_id, card_name, member_name]):
			print('Card ID, card name and member name cannot be None!')
			raise
		self.card_id, self.card_name, self.member_name = card_id, card_name, member_name
		self.tags = [k for k,v in groups.items() if self.member_name in v]
		if rarity not in rarity_list or type(idolized) != bool:
			print('Incorrect rarity!')
			raise
		self.rarity, self.promo, self.idolized = rarity, promo, idolized
		self.idolized = self.idolized or self.promo
		self.max_level, self.max_bond = max_level_dict[idolized][rarity], max_bond_dict[idolized][rarity]
		if self.promo:
			self.min_slot_num, self.max_slot_num = promo_slot_num_dict[rarity]
		else:
			self.min_slot_num, self.max_slot_num = slot_num_dict[rarity]
		self.level, self.bond = self.max_level, self.max_bond
		self.slot_num, self.used_slot_num, self.equipped_gems = self.min_slot_num, 0, []
		if main_attr not in attr_list:
			print('Incorrect main attribute!')
			raise
		self.main_attr = main_attr
		# stats_list = array([ [smile, pure, cool, price, exp, hp], ..., [smile, pure, cool, price, exp, hp] ])
		stats_list = np.array(stats_list)
		if stats_list.shape != (max_level_dict[True][rarity],6):
			print('Incorrect stats list!')
			raise
		self.stats_list = stats_list
		self.smile, self.pure, self.cool, self.hp = [stats_list[self.level-1][i] for i in [0,1,2,5]]
		if rarity != 'N' and not all([skill, cskill]):
			print('Cards with rarity higher than <N> must have skill and center skill!')
			raise
		self.skill, self.cskill = skill, cskill
	def __repr__(self, leader=True):
		lines = []
		if self.card_name != ' ':
			intro = '{0}: {1} - {2} {3}{4}, {5}'.format(self.card_id, self.member_name, self.card_name, self.rarity, '(t)' if self.idolized else '', self.main_attr)
		else:
			intro = '{0}: {1} {2}{3}, {4}'.format(self.card_id, self.member_name, self.rarity, '(t)' if self.idolized else '', self.main_attr)
		lines.append(intro + (', Promo Card' if self.promo else ''))
		if len(self.tags) == 3:
			lines.append('Group - {0}, {1}, {2}'.format(*self.tags))
		lines.append('| Level: {0}/{1} | Bond: {2}/{3} | Slot: {4}/[{5}-{6}] '.format(self.level, self.max_level, self.bond, self.max_bond, self.slot_num, self.min_slot_num, self.max_slot_num)
					 + '| Smile: {0} | Pure: {1} | Cool: {2} | HP:{3} |'.format(self.smile, self.pure, self.cool, self.hp))
		if self.rarity != 'N':
			lines.append('Skill - {0}'.format(repr(self.skill)))
			lines.append('Center Skill - {0}'.format(repr(self.cskill)))
		if len(self.equipped_gems) > 0:
			lines.append('Gems - {0}'.format(', '.join([gem.name for gem in self.equipped_gems])))
		string = '\n'.join(lines)
		return string
	def level_up(self, skill_level=None, slot_num=None, level=None, bond=None):
		is_valid = lambda x, min_val, max_val: x is None or (type(x) in [int, np.int64] and x <= max_val and x >= min_val)
		check = [is_valid(level, 1, self.max_level),
				 is_valid(bond, 0, self.max_bond),
				 is_valid(skill_level, 1, 8),
				 is_valid(slot_num, self.min_slot_num, self.max_slot_num)]
		is_none = [x is None for x in [level, bond, slot_num, skill_level]]
		if not all(check):
			attr_name = np.array(['Level', 'Bond', 'Skill Level', 'Slot Number'])
			print(self)
			print('{0} must be integer within valid range!'.format(', '.join(attr_name[[not x for x in check]])))
			raise
		not_none = [not x for x in is_none]
		new_attr = np.array([self.level, self.bond, self.slot_num, 0 if self.skill is None else self.skill.level], dtype=int)
		new_attr[not_none] = np.array([level, bond, slot_num, 0 if skill_level is None else skill_level])[not_none]
		self.level, self.bond, self.slot_num, skill_level = new_attr
		if self.skill is not None and skill_level in list(range(1,9)): 
			self.skill.set_level(skill_level)
		self.smile, self.pure, self.cool, self.hp = [self.stats_list[self.level-1][i] for i in [0,1,2,5]]
	def idolize(self, idolized=True, reset_slot=True):
		self.idolized = idolized or self.promo
		self.max_level, self.max_bond = max_level_dict[self.idolized][self.rarity], max_bond_dict[self.idolized][self.rarity]
		self.level, self.bond = self.max_level, self.max_bond
		self.smile, self.pure, self.cool, self.hp = [self.stats_list[self.level-1][i] for i in [0,1,2,5]]
		if reset_slot:
			if self.promo:
				self.min_slot_num, self.max_slot_num = promo_slot_num_dict[self.rarity]
			else:
				self.min_slot_num, self.max_slot_num = slot_num_dict[self.rarity]
			self.slot_num, self.equipped_gems = self.min_slot_num, []
	def equip_gem(self, gem_list):
		if len(set(gem_list)) < len(gem_list):
			print('Duplicated skill gems are not allowed!')
			raise
		gems = [GemSkill(name) for name in gem_list]
		slot_cost = sum([gem.cost for gem in gems])
		if slot_cost > self.slot_num:
			print('Slot number is not enough, cost is {0}, slot is {1}!'.format(slot_cost, self.slot_num))
			raise
		for gem in gems:
			if gem.constraint is None:
				continue
			elif gem.constraint in attr_list:
				if gem.constraint != self.main_attr:
					print('{0} requires {1}, card attribute is {2}'.format(gem.name, gem.constraint, self.main_attr))
					raise
			elif gem.constraint not in self.tags:
				print('{0} requires {1}, card tag is {2}'.format(gem.name, gem.constraint, self.tags))
				raise
		self.equipped_gems, self.used_slot_num = gems, slot_cost
	def card_strength(self, include_gem=True):
		# Base attribute value from naked card
		base_attr = np.array([getattr(self, attr.lower()) for attr in attr_list], dtype=float)
		# Bonus from bond
		bond_bonus = np.array([self.bond*(attr==self.main_attr) for attr in attr_list], dtype=float)
		# Compute card-only attribute: base+bond
		card_only_attr = base_attr + bond_bonus
		if not include_gem:
			strength = np.array(card_only_attr, dtype=int).tolist()
		else:
			gem_type_list = ['Kiss', 'Perfume', 'Ring', 'Cross']
			gem_matrix = {gem_type:np.zeros(3) for gem_type in gem_type_list}
			for gem in self.equipped_gems:
				gem_type = gem.name.split()[1]
				if gem_type in gem_type_list:
					gem_matrix[gem_type][attr_list.index(gem.attribute)] = gem.value / 100**(gem.effect=='attr_boost')
			strength = card_only_attr.copy()
			for gem_type in gem_type_list:
				if gem_type in ['Kiss', 'Perfume']:
					strength += gem_matrix[gem_type]
				elif gem_type in ['Ring', 'Cross']:
					strength += np.ceil(card_only_attr*gem_matrix[gem_type])
			strength = np.array(strength, dtype=int)
		return {k.lower()+'*':v for k,v in zip(attr_list, strength)}
	def general_strength(self, setting={'cskill1':None, 'cskill2':None, 'group_match':True, 'score_up_rate':1}):
		cskill1, cskill2, group_match, score_up_rate = setting.get('cskill1', None), setting.get('cskill2', None), setting.get('group_match', True), setting.get('score_up_rate', 1)
		# From LL Helper, one slot is equivalent to 5.2% bonus
		slot_bonus = 5.2/100 	
		# Skill gems costs 4 slots
		skillup_gem_cost = 4
		# Compute skill gain and strength per point per note
		if self.skill is not None:
			skill_gain, strength_per_pt_tap = self.skill.skill_gain(setting=setting)
		else:
			skill_gain, strength_per_pt_tap = 0, 0
		# Compute center skill points and corrected attribute
		if cskill1 is None and cskill2 is None:
			# LL Helper general strength
			# Average bonus ratio over all UR cards, including both main & alternative center skills, value should be close to 1.15
			center_bonus = 1.15
			# Compute amend attribute
			attr_val  = np.array([getattr(self, x.lower())/attr_match_factor**(x != self.main_attr) + self.bond*(x == self.main_attr) for x in attr_list])
			attr_val *= center_bonus
		else:
			# LL TeamBuilder rough strength
			center_bonus = np.ones(3)
			if cskill1 is not None:
				# For each attribute, only consider to equip gems with same color
				# Therefore center skill with different main attribution and base attribute does not benefit from gems
				if cskill1.main_attr in cskill1.base_attr:
					center_bonus[attr_list.index(cskill1.main_attr)] += cskill1.main_ratio/100
				if cskill1.bonus_range in self.tags:
					center_bonus[attr_list.index(cskill1.main_attr)] += cskill1.bonus_ratio/100
			if cskill2 is not None:
				if cskill2.main_attr in cskill2.base_attr:
					center_bonus[attr_list.index(cskill2.main_attr)] += cskill2.main_ratio/100
				if cskill2.bonus_range in self.tags:
					center_bonus[attr_list.index(cskill2.main_attr)] += cskill2.bonus_ratio/100
			# Compute amend attribute
			attr_val = np.array([getattr(self, x.lower())/attr_match_factor**(x != self.main_attr) + self.bond*(x == self.main_attr) for x in attr_list])
			attr_val *= center_bonus / group_match_factor**(1-group_match)
		# For different types of skill, compare cases with/without skill gem
		if self.skill is None:
			use_skill_gem = np.array([False]*3)
			attr_val = attr_val*(1+slot_bonus*self.slot_num)
			skill_strength = np.zeros(3)
		elif self.skill.effect_type in ['Weak Judge', 'Strong Judge']:
			gem_bonus, strength = 0.33, skill_gain * (1+slot_bonus*(self.slot_num-skillup_gem_cost)) * attr_val
			branch1 = attr_val * (1+slot_bonus*self.slot_num)
			branch2 = attr_val * (1+slot_bonus*(self.slot_num-skillup_gem_cost)) + gem_bonus*strength/(group_match_factor*attr_match_factor) * (self.slot_num>=4)
			use_skill_gem = branch2 > branch1
			attr_val = np.maximum(branch1, branch2)
			skill_strength = gem_bonus*strength*np.ones(3)
		elif self.skill.effect_type == 'Stamina Restore':
			gem_bonus, strength = 480, skill_gain*strength_per_pt_tap*np.ones(3)
			branch1 = attr_val * (1+slot_bonus*self.slot_num)
			branch2 = attr_val * (1+slot_bonus*(self.slot_num-skillup_gem_cost)) + gem_bonus*strength/score_up_rate/(group_match_factor*attr_match_factor) * (self.slot_num>=4)
			use_skill_gem = branch2 > branch1
			attr_val = np.maximum(branch1, branch2)
			skill_strength = gem_bonus*strength
		elif self.skill.effect_type == 'Score Up':
			gem_bonus, strength = 2.5, skill_gain*strength_per_pt_tap*np.ones(3)
			branch1 = attr_val * (1+slot_bonus*self.slot_num) + strength/(group_match_factor*attr_match_factor)
			branch2 = attr_val * (1+slot_bonus*(self.slot_num-skillup_gem_cost)) + gem_bonus*strength/score_up_rate/(group_match_factor*attr_match_factor) * (self.slot_num>=4)
			use_skill_gem = branch2 > branch1
			attr_val = np.maximum(branch1, branch2)
			skill_strength = strength*np.ones(3)
		summary = dict()
		for i, attr in enumerate(attr_list):
			summary[attr] = {'strength': int(attr_val[i]), 'use_skill_gem':use_skill_gem[i], 'skill_strength':int(skill_strength[i])}
		return summary
	def to_dict(self, attrs=None):
		if attrs is not None:
			res = {attr:getattr(self,attr) for attr in attrs}
		else:
			res = self.__dict__
			res.pop('stats_list', None)
		return res
	def copy(self):
		return deepcopy(self)
	@classmethod
	def fromJSON(cls, json_data, idolized=False):
		card_id, card_name, member_name = json_data['card_id'], json_data['card_name'], json_data['member_name']
		rarity, main_attr, stats_list = json_data['rarity'], json_data['main_attr'], json_data['stats_list']
		skill_data, cskill_data = json_data['skill'], json_data['cskill']
		if skill_data is not None:
			skill = Skill(skill_data['name'], skill_data['trigger_type'], skill_data['trigger_count'], 
						  skill_data['effect_type'], skill_data['odds_list'], skill_data['rewards_list'])
			cskill = CenterSkill(cskill_data['name'], cskill_data['main_attr'], cskill_data['base_attr'], 
								 cskill_data['main_ratio'], cskill_data['bonus_range'], cskill_data['bonus_ratio'])
		else:
			skill, cskill = None, None
		idolized, promo = idolized or json_data['promo'], json_data['promo'] 
		return cls(card_id, card_name, member_name, rarity, main_attr, stats_list, idolized, skill, cskill, promo)

def card_dataframe(cards):
	keys = [ 'card_name', 'card_id', 'member_name', 'main_attr',
			 'idolized', 'promo', 'rarity',
			 'level', 'max_level', 
			 'bond', 'max_bond', 
			 'hp', 'smile', 'pure', 'cool',
			 'skill', 'cskill', 
			 'slot_num', 'max_slot_num', 'equipped_gems', 'tags']
	columns = ['index'] + keys #+ ['skill_gain']
	if type(cards) == dict:
		data = []
		for own_id, card in cards.items():
			item = {'index':int(own_id)}
			item.update(card.to_dict(keys))
			data.append(item)
	elif type(cards) == list:
		data = []
		for own_id, card in enumerate(cards,1):
			item = {'index':int(own_id)}
			item.update(card.to_dict(keys))
			data.append(item)
	else:
		print('Incorrect input type, only dict, list are supported')
		raise
	df = pd.DataFrame(data, columns=columns)
	df = df.set_index('index').sort_index()
	df.index.name = ''
	return df