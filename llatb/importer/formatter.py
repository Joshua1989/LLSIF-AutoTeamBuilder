TB_member_dict = {	'高坂穂乃果':0, '絢瀬絵里':1, '南ことり':2, '園田海未':3, '星空凛':4, '西木野真姫':5, '東條希':6, '小泉花陽':7, '矢澤にこ':8, 
					'高海千歌':9, '桜内梨子':10, '松浦果南':11, '黒澤ダイヤ':12, '渡辺曜':13, '津島善子':14, '国木田花丸':15, '小原鞠莉':16, '黒澤ルビィ':17}
TB_skill_dict = { 	None:0, ('Note', 'Score Up'):1, ('Combo', 'Score Up'):1, ('Perfect', 'Score Up'):2, ('Time', 'Score Up'):3, 
				('Score', 'Score Up'):4, ('Star', 'Score Up'):5, ('Note', 'Stamina Restore'):6, ('Combo', 'Stamina Restore'):6, 
				('Time', 'Stamina Restore'):7, ('Perfect', 'Stamina Restore'):8, ('Note', 'Strong Judge'):9, ('Combo', 'Strong Judge'):9, 
				('Time', 'Strong Judge'):10}
TB_cskill1_dict = {None:0, 9:1, 12:2, 7:3, 6:4, 3:5}
TB_cskill2_dict = {None:0, 
				("μ's",3):1, ('Aqours',3):1, 
				('1st-year',6):2, ('2nd-year',6):2, ('3rd-year',6):2,
				('Printemps',6):3, ('lily white',6):3, ('BiBi',6):3, 
				('CYaRon！',6):3, ('AZALEA',6):3, ('Guilty Kiss',6):3,
				("μ's",1):4, ('Aqours',1):4, 
				('1st-year',2):5, ('2nd-year',2):5, ('3rd-year',2):5,
				('Printemps',2):6, ('lily white',2):6, ('BiBi',2):6, 
				('CYaRon！',2):6, ('AZALEA',2):6, ('Guilty Kiss',2):6}
TB_gem_skill_list = [	'Smile Kiss', 'Smile Perfume', 'Smile Aura', 'Smile Veil', 
					'Smile Ring (1st)', 'Smile Ring (2nd)', 'Smile Ring (3rd)', 
					'Smile Cross (1st)', 'Smile Cross (2nd)', 'Smile Cross (3rd)', 
					'Pure Kiss', 'Pure Perfume', 'Pure Aura', 'Pure Veil', 
					'Pure Ring (1st)', 'Pure Ring (2nd)', 'Pure Ring (3rd)', 
					'Pure Cross (1st)', 'Pure Cross (2nd)', 'Pure Cross (3rd)', 
					'Cool Kiss', 'Cool Perfume', 'Cool Aura', 'Cool Veil', 
					'Cool Ring (1st)', 'Cool Ring (2nd)', 'Cool Ring (3rd)', 
					'Cool Cross (1st)', 'Cool Cross (2nd)', 'Cool Cross (3rd)', 
					'Angel Heal', 'Princess Heal', 'Empress Heal', 
					'Angel Charm', 'Princess Charm', 'Empress Charm', 
					'Angel Trick', 'Princess Trick', 'Empress Trick']

def adjusted_card_stat(card):
	stat = card.card_strength(include_gem=False)
	return [stat[x] for x in ['smile*', 'pure*', 'cool*']]
def get_skill_stat(skill, level):
	res = [0 if skill is None else TB_skill_dict[(skill.trigger_type, skill.effect_type)]]
	res += [skill.trigger_count, skill.reward_list[level-1], skill.odds_list[level-1]/100]
	return res
def get_cskill_stat(cskill):
	return [0 if cskill is None else TB_cskill1_dict[cskill.main_ratio], 
			0 if cskill is None or cskill.bonus_range is None else TB_cskill2_dict[(cskill.bonus_range, cskill.bonus_ratio)]]