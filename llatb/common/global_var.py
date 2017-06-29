import numpy as np
# Card Skill relevant
trigger_type_list = ['Time', 'Note', 'Combo', 'Score', 'Perfect', 'Star']
trigger_str_dict = {'Time': 'Triggers every {0} seconds.',
					'Note': 'Triggers every {0} notes.',
					'Combo': 'Triggers every {0} combo.',
					'Score': 'Triggers when score reaches a multiple of {0}.',
					'Perfect': 'Triggers every {0} perfect notes.',
					'Star': 'Triggers every {0} perfect star note.'}
effect_type_list = ['Weak Judge', 'Score Up', 'Stamina Restore', 'Strong Judge']
effect_str_dict = {'Weak Judge': 'slightly raise the accuracy judge for {0} seconds. ',
				   'Score Up': 'add {0} score points. ',
				   'Stamina Restore': 'restore {0} stamina points. ',
				   'Strong Judge': 'raise the accuracy judge for {0} seconds. '}
attr_list = ['Smile', 'Pure', 'Cool']
attr_color = {'Smile':'red', 'Pure':'green', 'Cool':'blue'}
bonus_range_list = ["μ's", 'Aqours', '1st-year', '2nd-year', '3rd-year',
					'Printemps', 'lily white', 'BiBi', 'CYaRon！', 'AZALEA', 'Guilty Kiss']
# Gem Skill relevant
attr_list = ['Smile', 'Pure', 'Cool']
gem_skill_dict = {'Smile Kiss': 		{'attribute':'Smile',	'constraint':None,			'cost':1,	'effect':'attr_add',	'value': 200},
				  'Pure Kiss': 			{'attribute':'Pure',	'constraint':None,			'cost':1,	'effect':'attr_add',	'value': 200},
				  'Cool Kiss': 			{'attribute':'Cool',	'constraint':None,			'cost':1,	'effect':'attr_add',	'value': 200},
				  'Smile Perfume': 		{'attribute':'Smile',	'constraint':None,			'cost':2,	'effect':'attr_add',	'value': 450},
				  'Pure Perfume': 		{'attribute':'Pure',	'constraint':None,			'cost':2,	'effect':'attr_add',	'value': 450},
				  'Cool Perfume': 		{'attribute':'Cool',	'constraint':None,			'cost':2,	'effect':'attr_add',	'value': 450},
				  'Smile Ring (1st)': 	{'attribute':'Smile',	'constraint':'1st-year',	'cost':2,	'effect':'attr_boost',	'value': 10.0},
				  'Pure Ring (1st)': 	{'attribute':'Pure',	'constraint':'1st-year',	'cost':2,	'effect':'attr_boost',	'value': 10.0},
				  'Cool Ring (1st)': 	{'attribute':'Cool',	'constraint':'1st-year',	'cost':2,	'effect':'attr_boost',	'value': 10.0},
				  'Smile Ring (2nd)': 	{'attribute':'Smile',	'constraint':'2nd-year',	'cost':2,	'effect':'attr_boost',	'value': 10.0},
				  'Pure Ring (2nd)': 	{'attribute':'Pure',	'constraint':'2nd-year',	'cost':2,	'effect':'attr_boost',	'value': 10.0},
				  'Cool Ring (2nd)': 	{'attribute':'Cool',	'constraint':'2nd-year',	'cost':2,	'effect':'attr_boost',	'value': 10.0},
				  'Smile Ring (3rd)': 	{'attribute':'Smile',	'constraint':'3rd-year',	'cost':2,	'effect':'attr_boost',	'value': 10.0},
				  'Pure Ring (3rd)': 	{'attribute':'Pure',	'constraint':'3rd-year',	'cost':2,	'effect':'attr_boost',	'value': 10.0},
				  'Cool Ring (3rd)': 	{'attribute':'Cool',	'constraint':'3rd-year',	'cost':2,	'effect':'attr_boost',	'value': 10.0},
				  'Smile Cross (1st)': 	{'attribute':'Smile',	'constraint':'1st-year',	'cost':3,	'effect':'attr_boost',	'value': 16.0},
				  'Pure Cross (1st)': 	{'attribute':'Pure',	'constraint':'1st-year',	'cost':3,	'effect':'attr_boost',	'value': 16.0},
				  'Cool Cross (1st)': 	{'attribute':'Cool',	'constraint':'1st-year',	'cost':3,	'effect':'attr_boost',	'value': 16.0},
				  'Smile Cross (2nd)': 	{'attribute':'Smile',	'constraint':'2nd-year',	'cost':3,	'effect':'attr_boost',	'value': 16.0},
				  'Pure Cross (2nd)': 	{'attribute':'Pure',	'constraint':'2nd-year',	'cost':3,	'effect':'attr_boost',	'value': 16.0},
				  'Cool Cross (2nd)': 	{'attribute':'Cool',	'constraint':'2nd-year',	'cost':3,	'effect':'attr_boost',	'value': 16.0},
				  'Smile Cross (3rd)': 	{'attribute':'Smile',	'constraint':'3rd-year',	'cost':3,	'effect':'attr_boost',	'value': 16.0},
				  'Pure Cross (3rd)': 	{'attribute':'Pure',	'constraint':'3rd-year',	'cost':3,	'effect':'attr_boost',	'value': 16.0},
				  'Cool Cross (3rd)': 	{'attribute':'Cool',	'constraint':'3rd-year',	'cost':3,	'effect':'attr_boost',	'value': 16.0},
				  'Smile Aura': 		{'attribute':'Smile',	'constraint':None,			'cost':3,	'effect':'team_boost',	'value': 1.8},
				  'Pure Aura': 			{'attribute':'Pure',	'constraint':None,			'cost':3,	'effect':'team_boost',	'value': 1.8},
				  'Cool Aura': 			{'attribute':'Cool',	'constraint':None,			'cost':3,	'effect':'team_boost',	'value': 1.8},
				  'Smile Veil': 		{'attribute':'Smile',	'constraint':None,			'cost':4,	'effect':'team_boost',	'value': 2.4},
				  'Pure Veil': 			{'attribute':'Pure',	'constraint':None,			'cost':4,	'effect':'team_boost',	'value': 2.4},
				  'Cool Veil': 			{'attribute':'Cool',	'constraint':None,			'cost':4,	'effect':'team_boost',	'value': 2.4},
				  'Princess Charm': 	{'attribute':None,		'constraint':'Smile',		'cost':4,	'effect':'score_boost',	'value': 2.5},
				  'Angel Charm': 		{'attribute':None,		'constraint':'Pure',		'cost':4,	'effect':'score_boost',	'value': 2.5},
				  'Empress Charm': 		{'attribute':None,		'constraint':'Cool',		'cost':4,	'effect':'score_boost',	'value': 2.5},
				  'Princess Heal': 		{'attribute':None,		'constraint':'Smile',		'cost':4,	'effect':'heal_boost',	'value': 480},
				  'Angel Heal': 		{'attribute':None,		'constraint':'Pure',		'cost':4,	'effect':'heal_boost',	'value': 480},
				  'Empress Heal': 		{'attribute':None,		'constraint':'Cool',		'cost':4,	'effect':'heal_boost',	'value': 480},
				  'Princess Trick': 	{'attribute':'Smile',	'constraint':'Smile',		'cost':4,	'effect':'judge_boost',	'value': 33.0},
				  'Angel Trick': 		{'attribute':'Pure',	'constraint':'Pure',		'cost':4,	'effect':'judge_boost',	'value': 33.0},
				  'Empress Trick': 		{'attribute':'Cool',	'constraint':'Cool',		'cost':4,	'effect':'judge_boost',	'value': 33.0}}
gem_skill_id_dict = { 1:'Smile Kiss',		 	 2:'Pure Kiss',				 3:'Cool Kiss',
					  4:'Smile Perfume',		 5:'Pure Perfume',			 6:'Cool Perfume',
					  7:'Smile Ring (1st)',		 8:'Pure Ring (1st)',		 9:'Cool Ring (1st)',
					 10:'Smile Ring (2nd)',		11:'Pure Ring (2nd)',		12:'Cool Ring (2nd)',
					 13:'Smile Ring (3rd)',		14:'Pure Ring (3rd)',		15:'Cool Ring (3rd)',
					 16:'Smile Cross (1st)',	17:'Pure Cross (1st)',		18:'Cool Cross (1st)',
					 19:'Smile Cross (2nd)',	20:'Pure Cross (2nd)',		21:'Cool Cross (2nd)',
					 22:'Smile Cross (3rd)',	23:'Pure Cross (3rd)',		24:'Cool Cross (3rd)',
					 25:'Smile Aura',			26:'Pure Aura',				27:'Cool Aura',
					 28:'Smile Veil',			29:'Pure Veil',				30:'Cool Veil',
					 31:'Princess Charm',		32:'Princess Heal',			33:'Princess Trick',
					 34:'Angel Charm',			35:'Angel Heal',			36:'Angel Trick',
					 37:'Empress Charm',		38:'Empress Heal',			39:'Empress Trick'}
# Center Skill relevant
muse = np.array(['Kosaka Honoka', 'Minami Kotori', 'Sonoda Umi', 
			   'Koizumi Hanayo', 'Hoshizora Rin', 'Nishikino Maki', 
			   'Ayase Eli', 'Tojo Nozomi', 'Yazawa Nico'])
Aqours = np.array(['Takami Chika', 'Sakurauchi Riko', 'Watanabe You', 
			   'Kurosawa Ruby', 'Tsushima Yoshiko', 'Kunikida Hanamaru', 
			   'Ohara Mari', 'Matsuura Kanan', 'Kurosawa Dia'])
groups = {"μ's":muse, 'Aqours':Aqours,
		  '1st-year':np.concatenate((muse[[3,4,5]], Aqours[[3,4,5]])),
		  '2nd-year':np.concatenate((muse[[0,1,2]], Aqours[[0,1,2]])),
		  '3rd-year':np.concatenate((muse[[6,7,8]], Aqours[[6,7,8]])),
		  'Printemps':muse[[0,1,3]],  'lily white':muse[[2,4,7]], 'BiBi':muse[[5,6,8]],
		  'CYaRon！':Aqours[[0,2,3]], 'AZALEA':Aqours[[5,7,8]],    'Guilty Kiss':Aqours[[1,3,6]]}
# Card relevant
rarity_list = ['N', 'R', 'SR', 'SSR', 'UR']
max_level_dict = {False:{'N':30, 'R':40, 'SR':60, 'SSR':70, 'UR':80},
				  True: {'N':40, 'R':60, 'SR':80, 'SSR':90, 'UR':100}}
max_bond_dict = {False:{'N':25, 'R':100, 'SR':250, 'SSR':375, 'UR':500},
				 True: {'N':50, 'R':200, 'SR':500, 'SSR':750, 'UR':1000}}
slot_num_dict = {'N':[0,1], 'R':[1,2], 'SR':[2,4], 'SSR':[3,6], 'UR':[4,8]}
promo_slot_num_dict = {'R':[1,1], 'SR':[1,1], 'UR':[2,2]}
# Game Scoring relevant
accuracy_list = ['Perfect', 'Great', 'Good', 'Bad', 'Miss']
base_score_factor = 0.01
accuracy_factor = {'Perfect':1.25, 'Great':1.00, 'Good':1.00, 'Bad':0.50, 'Miss':0.00}
combo_factor_aux = { 0:1.00,	 1:1.10,	 2:1.15,	 3:1.15,
					 4:1.20,	 5:1.20,	 6:1.20,	 7:1.20,
					 8:1.25,	 9:1.25,	10:1.25,	11:1.25,
					12:1.30,	13:1.30,	14:1.30,	15:1.30}
def combo_factor(combo):
	return 1.35 if combo > 800 else combo_factor_aux[int((combo-1)/50)]
long_factor = 1.0
swing_factor = 0.5
attr_match_factor = 1.10
group_match_factor = 1.10
hp_penalty_dict = { False:{ 'Perfect':0, 'Great':0, 'Good':0, 'Bad':1, 'Miss':2 },
					True: { 'Perfect':0, 'Great':0, 'Good':2, 'Bad':2, 'Miss':4 } }
# Medley Festival / Challenge Festival boosts
purchase_boost = ['Perfect Support', 'Tap Score Up', 'Skill Up', 'Stamina Restore']
