import math
from llatb.common.global_var import attr_list, bonus_range_list

class CenterSkill:
	def __init__(self, name=None, main_attr=None, base_attr=None, 
				 main_ratio=None, bonus_range=None, bonus_ratio=None):
		self.name = None
		self.main_attr, self.base_attr, self.main_ratio = None, None, None
		self.bonus_range, self.bonus_ratio = None, None
		
		if name is None:
			return
		else:
			self.name = name
			if not any([main_attr,base_attr]):
				print('The main attribute and main odds must be given!')
				raise
			if main_attr not in attr_list or base_attr not in attr_list:
				print('Incorrect attribute type!')
				raise
			base_attr = main_attr if base_attr is None else base_attr
			self.main_attr, self.base_attr, self.main_ratio = main_attr, base_attr, main_ratio
			if bonus_range is not None and bonus_range not in bonus_range_list:
				print('Incorrect bonus range!')
				raise
			if sum(map(lambda x: x is None, [bonus_range, bonus_ratio])) == 1:
				print('Bonus range and bonus odds should both be None or both not None')
				raise
			self.bonus_range, self.bonus_ratio = bonus_range, bonus_ratio
	def __repr__(self):
		if self.name is None:
			return 'NA'
		else:
			if self.main_attr == self.base_attr:
				skill_str = "Raise the team's {0} by {1}%. ".format(self.main_attr, self.main_ratio)
			else:
				skill_str = "Raise the team's {0} by {1}% of its {2}. ".format(self.main_attr, self.main_ratio, self.base_attr)
			if self.bonus_range is not None:
				bonus_str = 'Additional effect: raise the {0} contribution of {1} members by {2}%.'.format(self.main_attr, self.bonus_range, self.bonus_ratio)
			else:
				bonus_str = ''
		return self.name + ': ' + skill_str + bonus_str
	def __str__(self):
		descr = '{0}+{1}{2}%'.format(self.main_attr, self.base_attr, self.main_ratio)
		if self.bonus_ratio is not None:
			descr += '/{0}{1}%'.format(self.bonus_range, self.bonus_ratio)
		return descr
	def is_equal(self, cskill):
		if cskill is None: 
			return False
		else:
			keys = ['main_attr', 'base_attr', 'main_ratio', 'bonus_range', 'bonus_ratio']
			return all([getattr(self,x)==getattr(cskill,x) for x in keys])