import numpy as np
import pandas as pd
import json, sqlite3
from llatb.common.config import unit_db_dir
from llatb.common.global_var import *
from llatb.framework.card import Card

class Team:
	def __init__(self, card_list):
		if type(card_list) != list or len(card_list) != 9:
			print('9 cards are required to build a team!')
			raise
		self.card_list = card_list
	def __getitem__(self, slice):
		return self.card_list[slice]
	def __repr__(self):
		def show_card(card, pos, center=False):
			lines = []
			lines.append('Position {0} '.format(pos) + ('(Center)' if center else ''))
			if card.card_name != ' ':
				intro = '{0}: {1} - {2} {3}{4}, {5}'.format(card.card_id, card.member_name, card.card_name, card.rarity, '(t)' if card.idolized else '', card.main_attr)
			else:
				intro = '{0}: {1} {2}{3}, {4}'.format(card.card_id, card.member_name, card.rarity, '(t)' if card.idolized else '', card.main_attr)
			lines.append(intro + (', Promo Card' if card.promo else ''))
			lines.append('| Smile: {0} | Pure: {1} | Cool: {2} | HP:{3} |'.format(card.smile, card.pure, card.cool, card.hp))
			lines.append('Gems [{0}/{1}] - {2}'.format(card.used_slot_num, card.slot_num, ', '.join([gem.name for gem in card.equipped_gems])))
			if card.rarity != 'N':
				lines.append('Skill - {0}'.format(repr(card.skill)))
				if center:
					lines.append('Center Skill - {0}'.format(repr(card.cskill)))
			string = '\n'.join(lines)
			return string
		return '\n\n'.join([show_card(self.card_list[4],pos=5,center=True)] + [show_card(card, pos=pos) for pos, card in enumerate(self.card_list, 1) if pos != 5])
	def center(self):
		return self.card_list[4]
	def team_strength(self, guest_cskill=None):
		card_list = self.card_list
		# Compute card-only attribute: base+bond and card UI attribute: base+bond+individual gem
		card_only_attr, displayed_card_attr = np.zeros((9,3)), np.zeros((9,3))
		for i, card in enumerate(card_list):
			res = card.card_strength(include_gem=False)
			card_only_attr[i,:] = np.array([res[x.lower()+'*'] for x in attr_list])
			res = card.card_strength(include_gem=True)
			displayed_card_attr[i,:] = np.array([res[x.lower()+'*'] for x in attr_list])

		# Count number of team boost gems
		gem_type_list = ['Aura', 'Veil']
		gem_value = {'Aura':1.8/100, 'Veil':2.4/100}
		gem_count = {'Aura':np.zeros((1,3)), 'Veil':np.zeros((1,3))}
		for i, card in enumerate(card_list):
			for gem in card.equipped_gems:
				gem_type = gem.name.split()[1]
				if gem_type in gem_type_list:
					gem_count[gem_type][0, attr_list.index(gem.attribute)] += 1
		# Compute team boost bonus
		team_boost_bonus_detail = np.zeros((9,3))
		for gem_type in gem_type_list:
			team_boost_bonus_detail += gem_count[gem_type]*np.ceil(card_only_attr*gem_value[gem_type])
		# Compute center SIS bonus
		SIS_bonus = np.array(team_boost_bonus_detail.sum(axis=0), dtype=int)

		card_gem_attr = displayed_card_attr + team_boost_bonus_detail
		final_attr = card_gem_attr.copy()
		team_cskill_bonus_detail, team_cskill_bonus = np.zeros((9,3)), np.zeros(3)
		if card_list[4].cskill is not None:
			cskill = card_list[4].cskill
			# Bonus from center skill (main part)
			main_attr_idx = attr_list.index(cskill.main_attr)
			base_attr_idx = attr_list.index(cskill.base_attr)
			team_cskill_bonus_detail[:,main_attr_idx] += np.ceil(card_gem_attr[:, base_attr_idx] * cskill.main_ratio/100)
			# Bonus from center skill (additional part, if applicable)
			if cskill.bonus_range is not None:
				temp = np.array([card.member_name in groups[cskill.bonus_range] for card in card_list]) * cskill.bonus_ratio/100
				team_cskill_bonus_detail[:,main_attr_idx] += np.ceil(card_gem_attr[:, main_attr_idx] * temp)
			# Add center skill bonus
			final_attr += team_cskill_bonus_detail
			# Compute center skill bonus
			team_cskill_bonus = team_cskill_bonus_detail.sum(axis=0)

		guest_cskill_bonus_detail, guest_cskill_bonus = np.zeros((9,3)), np.zeros(3, dtype=int)
		if guest_cskill is not None:
			cskill = guest_cskill
			# Bonus from center skill (main part)
			main_attr_idx = attr_list.index(cskill.main_attr)
			base_attr_idx = attr_list.index(cskill.base_attr)
			guest_cskill_bonus_detail[:,main_attr_idx] += np.ceil(card_gem_attr[:, base_attr_idx] * cskill.main_ratio/100)
			# Bonus from center skill (additional part, if applicable)
			if cskill.bonus_range is not None:
				temp = np.array([card.member_name in groups[cskill.bonus_range] for card in card_list]) * cskill.bonus_ratio/100
				guest_cskill_bonus_detail[:,main_attr_idx] += np.ceil(card_gem_attr[:, main_attr_idx] * temp)
			# Add center skill bonus
			final_attr += guest_cskill_bonus_detail
			# Compute center skill bonus
			guest_cskill_bonus = guest_cskill_bonus_detail.sum(axis=0)

		int_list = lambda x: np.array(x, dtype=int).tolist()
		res = {'team_total':np.array(final_attr, dtype=int).sum(axis=0).tolist(),
		       'center_skill_bonus':int_list(team_cskill_bonus+guest_cskill_bonus),
		       'team_center_skill_bonus':int_list(team_cskill_bonus),
		       'guest_center_skill_bonus':int_list(guest_cskill_bonus),
		       'center_SIS_bonus':int_list(SIS_bonus),
		       'displayed_card_attr':int_list(displayed_card_attr),
		       'before_C_attr':int_list(card_gem_attr),
		       'final_card_attr':int_list(final_attr)}
		return res
	def compute_expected_total_score(self, live, opt={}, verbose=False):
		def generate_setting(live):
			res = { key:getattr(live, key) for key in ['note_number', 'duration', 'star_density', 'note_type_dist', 'perfect_rate'] }
			res['attr_group_factor'] = 1
			res['team_strength'] = opt.get('rough_team_strength', 80000)
			res['score_up_rate'] = 1 + opt.get('score_up_bonus',0)
			res['skill_up_rate'] = 1 + opt.get('skill_up_bonus',0)
			return res
		def compute_attr_group_factor(card):
			return attr_match_factor**(live.attr==card.main_attr) * group_match_factor**(live.group in card.tags)
		def rough_total_cover_rate():
			# Compute team total cover rate
			temp = np.ones(9)
			for i, card in enumerate(self.card_list):
				if card.skill is not None and card.skill.effect_type in ['Weak Judge', 'Strong Judge']:
					new_setting = setting.copy()
					new_setting['attr_group_factor'] = compute_attr_group_factor(card)
					temp[i] -= card.skill.skill_gain(setting=new_setting)[0]
			return 1 - temp.prod()
		def amend_perfect_rate_and_team_strength(CR):
			# Compute team total attribute when judge skill is not active and active
			guest_cskill = opt.get('guest_cskill', None)
			res = self.team_strength(guest_cskill)
			temp = np.array(res['displayed_card_attr'])
			total = np.zeros((2,3))
			for i,card in enumerate(self.card_list):
				total += temp[i,:]
				for gem in card.equipped_gems:
					if gem.effect == 'judge_boost':
						attr_idx = attr_list.index(gem.attribute)
						total[1,attr_idx] += gem.value/100*temp[i,attr_idx]
			total += np.array(res['center_skill_bonus']) + np.array(res['center_SIS_bonus'])
			# Amend perfect rate and team strength
			perfect_rate = 1 - (1-live.perfect_rate) * (1-CR)
			attr_idx = attr_list.index(live.attr)
			team_strength = (1-CR) * total[0,attr_idx] + CR * total[1,attr_idx]
			return perfect_rate, team_strength
		def compute_total_skill_strength(perfect_rate, team_strength):
			# Compute the skill strength for all Score Up and Stamina Restore skills
			total, opt = 0, {'perfect_rate':perfect_rate, 'team_strength':team_strength}
			for card in self.card_list:
				new_setting = setting.copy()
				new_setting.update(opt)
				new_setting['attr_group_factor'] = compute_attr_group_factor(card)
				if card.skill is not None and card.skill.effect_type == 'Score Up':
					skill_gain, score_coeff = card.skill.skill_gain(setting=new_setting)
					has_charm = any(['Charm' in gem.name for gem in card.equipped_gems])
					total += skill_gain * score_coeff * 2.5**has_charm
				elif card.skill is not None and card.skill.effect_type == 'Stamina Restore':
					skill_gain, score_coeff = card.skill.skill_gain(setting=new_setting)
					has_heal = any(['Heal' in gem.name for gem in card.equipped_gems])
					total += skill_gain * score_coeff * 480 * has_heal
			return total
		def compute_average_position_bonus():
			# Compute same group, same attribute bonus for each position
			attr_group_bonus = np.array([compute_attr_group_factor(card) for card in self.card_list])
			# Compute combo weight fraction of the live, 
			# note the last one is total which equals to 1 and the position in note list is given in clockwise
			combo_weight_fraction = live.combo_weight_fraction
			return (attr_group_bonus * combo_weight_fraction).sum()

		setting = generate_setting(live)
		CR = rough_total_cover_rate()
		amend_perfect_rate, amend_team_strength = amend_perfect_rate_and_team_strength(CR)
		total_skill_strength = compute_total_skill_strength(amend_perfect_rate, amend_team_strength)
		average_pos_bonus = compute_average_position_bonus()
		expected_total_score  = amend_team_strength * live.pts_per_strength * average_pos_bonus * setting['score_up_rate']
		expected_total_score += total_skill_strength * live.pts_per_strength
		if verbose:
			print('Expected Team Judge Cover Rate: {0:.4f}%'.format(CR*100))
			print('Amend Team Strength: {0}'.format(int(amend_team_strength)))
			print('Total Skill Strength: {0}'.format(int(total_skill_strength)))
			print('Point per Strength: {0:.4f}'.format(live.pts_per_strength))
			print('Average Note/Combo/Judge Bonus {0:.4f}'.format(live.average_bonus))
			print('Average Position Bonus {0:.4f}'.format(average_pos_bonus))
			print('Expected Total Score {0}'.format(int(expected_total_score)))
		return int(expected_total_score)
	def to_LLHelper(self, filename):
		def card_string(card):
			card_field_list = ['smile', 'pure', 'cool', 'skilllevel', 'cardid', 'mezame']
			gem_field_list = ['gemnum', 'gemsinglepercent', 'gemallpercent', 'gemskill', 'gemacc', 'maxcost']
			gem_data = {k:0 for k in gem_field_list}
			for gem in card.equipped_gems:
				if 'Kiss' in gem.name and gem.attribute == card.main_attr:
					gem_data['gemnum'] += 200
				if 'Perfume' in gem.name and gem.attribute == card.main_attr:
					gem_data['gemnum'] += 450
				if 'Ring' in gem.name and gem.attribute == card.main_attr:
					gem_data['gemsinglepercent'] += 0.1
				if 'Cross' in gem.name and gem.attribute == card.main_attr:
					gem_data['gemsinglepercent'] += 0.16
				if 'Aura' in gem.name and gem.attribute == card.main_attr:
					gem_data['gemallpercent'] += 0.018
				if 'Veil' in gem.name and gem.attribute == card.main_attr:
					gem_data['gemallpercent'] += 0.024
				if 'Charm' in gem.name or 'Heal' in gem.name:
					gem_data['gemskill'] = 1
				if 'Trick' in gem.name:
					gem_data['gemacc'] = 1
			gem_data['maxcost'] = card.slot_num
			field_name = card_field_list + gem_field_list
			field_val  = [  card.smile + card.bond * (card.main_attr=='Smile'), 
							card.pure + card.bond * (card.main_attr=='Pure'), 
							card.cool + card.bond * (card.main_attr=='Cool'), 
							0 if card.skill is None else card.skill.level, card.card_id, card.idolized]
			field_val += [gem_data[x] for x in gem_field_list]
			temp = ['%22{0}%22:%22{1}%22'.format(k,v if type(v) != bool else int(v)) for k,v in zip(field_name, field_val)]
			return '%7B'+','.join(temp)+'%7D'
		card_strings = [card_string(card) for card in self.card_list]
		content = '[{0}]'.format(','.join(card_strings))
		with open(filename, 'w') as fp:
			fp.write(content)
		print('File saved to', filename)
	def to_ieb(self, filename):
		gem_id_dict = {v:k for k,v in gem_skill_id_dict.items()}
		cid_uid_dict = {v:k for k,v in sqlite3.connect(unit_db_dir).cursor().execute("SELECT unit_id, unit_number FROM unit_m").fetchall()}
		def card_dict(card):
			res = {'love':int(card.bond), 'rank':int(card.idolized)+1, 'level':int(card.level), 'unit_skill_level':int(card.skill.level),
				   'unit_id':cid_uid_dict[card.card_id], 'removable':[gem_id_dict[gem.name] for gem in card.equipped_gems]}
			return res
		content = [0] + [card_dict(card) for card in self.card_list]
		with open(filename, 'w') as fp:
			fp.write(json.dumps(content))
		print('File saved to', filename)