import numpy as np

class SkillTracker:
	def __init__(self, card, skill_up=0):
		skill = card.skill
		if skill is None: 
			self.trigger_type = None
			return
		# Skill type
		self.trigger_type = skill.trigger_type
		self.effect_type = skill.effect_type
		# Skill data
		self.cooldown = skill.trigger_count
		self.prob = np.minimum(100, (1+skill_up) * skill.odds) / 100
		self.reward = skill.reward
		self.duration = skill.reward if self.effect_type in ['Weak Judge', 'Strong Judge'] else 0
		# Skill gem
		self.score_boost, self.heal_boost = 1, 0
		for gem in card.equipped_gems:
			if gem.effect == 'score_boost':
				self.score_boost = gem.value
			elif gem.effect == 'heal_boost':
				self.heal_boost = gem.value
		self.init_state()
	def init_state(self):
		# Accumulated trigger count
		self.curr_state = 0
		# Inherit status and remaining active time for judge skills
		self.inherit, self.remain = False, 0
		# Cumulate reward
		self.cum_base_score = 0
		self.cum_score = 0
		self.cum_hp = 0
		self.cum_judge = 0
		self.cum_weak_judge = 0
	def update(self, note, max_hp):
		# Return: score bonus, hp restore, strong judge time, weak judge time
		reward = {'score':0, 'hp':0, 'weak_judge':0, 'judge':0}
		if self.trigger_type is None: return reward
		# If update current status of the skill
		if self.trigger_type == 'Time':
			self.curr_state += note['time_elapse']
		elif 'h' not in note['index']:
			if self.trigger_type == 'Note':
				self.curr_state += 1
			elif self.trigger_type == 'Combo':
				self.curr_state += note['accuracy*'] in ['Perfect', 'Great']
			elif self.trigger_type == 'Score':
				self.curr_state += note['score']
			elif self.trigger_type == 'Perfect':
				self.curr_state += note['accuracy*'] == 'Perfect'
			elif self.trigger_type == 'Star':
				self.curr_state += note['star'] and note['accuracy*'] == 'Perfect'
			else:
				print('Unknown trigger type: {0}'.format(self.trigger_type))
				raise
		
		# If the judge skill is inherited and last skill just ended, try to trigger it
		idle_time = -np.minimum(0, self.remain - note['time_elapse'])
		self.remain = np.maximum(0, self.remain - note['time_elapse'])
		if self.inherit and self.remain == 0:
			self.inherit = False
			self.curr_state = self.curr_state % self.cooldown
			active = np.random.random() < self.prob
			self.remain = (self.duration - idle_time) * active
			if self.effect_type == 'Weak Judge':
				reward = {'score':0, 'hp':0, 'weak_judge':self.remain, 'judge':0}
				self.cum_weak_judge += self.duration
			elif self.effect_type == 'Strong Judge':
				reward = {'score':0, 'hp':0, 'weak_judge':0, 'judge':self.remain}
				self.cum_judge += self.duration * active
			else:
				print('Unknown effect type: {0}'.format(self.effect_type))
				raise
				
		# If the current status exceeds the cooldown, activate skill by chance
		if self.curr_state >= self.cooldown:
			self.curr_state = self.curr_state % self.cooldown
			active = np.random.random() < self.prob
			if self.effect_type == 'Weak Judge':
				# If no inherit and skill is not active, try to trigger it
				if not self.inherit and self.remain == 0:
					self.remain = (self.duration - self.curr_state) * active
					reward = {'score':0, 'hp':0, 'weak_judge':self.remain, 'judge':0}
					self.cum_weak_judge += self.duration
				# If no inherit and skill is active, set inherit to True
				elif not self.inherit and self.remain > 0:
					self.inherit = True
				# If interit and skill is active, encounter self-overlap loss
			elif self.effect_type == 'Strong Judge':
				# If no inherit and skill is not active, try to trigger it
				if not self.inherit and self.remain == 0:
					self.remain = self.duration * active
					reward = {'score':0, 'hp':0, 'weak_judge':0, 'judge':self.remain}
					self.cum_judge += self.duration * active
				# If no inherit and skill is active, set inherit to True
				elif not self.inherit and self.remain > 0:
					self.inherit = True
				# If interit and skill is active, encounter self-overlap loss
			elif self.effect_type == 'Stamina Restore':
				if note['hp'] == max_hp and self.heal_boost > 0:
					reward = {'score':self.reward*self.heal_boost * active, 'hp':0, 'weak_judge':0, 'judge':0}
					self.cum_score += self.reward*self.heal_boost * active
				else:
					reward = {'score':0, 'hp':self.reward * active, 'weak_judge':0, 'judge':0}
					self.cum_hp += self.reward * active
			elif self.effect_type == 'Score Up':
				try:
					reward = {'score':self.reward*self.score_boost * active, 'hp':0, 'weak_judge':0, 'judge':0}
					self.cum_score += self.reward*self.score_boost * active
				except:
					print(self.reward, self.score_boost, active)
					raise
			else:
				print('Unknown effect type: {0}'.format(self.effect_type))
				raise
		return reward