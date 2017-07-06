import numpy as np
from llatb.common.global_var import gem_skill_dict, gem_skill_id_dict

class GemSkill:
	def __init__(self, name):
		if gem_skill_dict.get(name) is None:
			print('Invalid skill gem: {0}!'.format(name))
			raise
		self.id = {v:k for k,v in gem_skill_id_dict.items()}[name]
		skill = gem_skill_dict[name]
		self.name = name
		self.attribute, self.constraint = skill['attribute'], skill['constraint']
		self.cost, self.effect, self.value = skill['cost'], skill['effect'], skill['value']
	def __repr__(self):
		if self.effect == 'attr_add':
			return "Increases the card's {0} stat by {1}".format(self.attribute, self.value)
		elif self.effect == 'attr_boost':
			return "Increases the card's {0} stat by {1}%, can only be equipped on {2} members".format(self.attribute, int(self.value), self.constraint)
		elif self.effect == 'team_boost':
			return "Increases the team's {0} stat by {1:.1f}%".format(self.attribute, self.value)
		elif self.effect == 'score_boost':
			return "Multiplies the card's Score Up skill power by {0}, can only be equipped on {1} members".format(self.value, self.constraint)
		elif self.effect == 'heal_boost':
			return "When Stamina is full, increases score by {0}x[recovery value], can only be equipped on {1} members".format(self.value, self.constraint)
		elif self.effect == 'judge_boost':
			return "Increases the card's Smile stat by {0}% when a Perfect Lock is active, can only be equipped on {1} members".format(int(self.value), self.constraint)
		else:
			print('Invalid skill gem effect!')
			raise