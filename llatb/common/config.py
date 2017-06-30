import os
from pathlib import Path
from llatb.common.global_var import gem_skill_dict, gem_skill_id_rev_dict

# Comprehensive card information
card_archive_dir = 'assets/data_base.json'
# Comprehensive live basic information
live_archive_dir = 'assets/live_data_base.json'
# unit_id and unit_number correspondence
unit_db_dir = 'assets/unit.db_'

# URL for retrieving card information and downloading resource
card_info_base_url = 'https://sif.kirara.ca/checklist'
def card_info_url(card_id):
	return 'https://sif.kirara.ca/card/{0}'.format(card_id)
def icon_download_url(card_id, idolized):
	return 'http://r.llsif.win/git/SIFStatic/icon/{1}/{0}.png'.format(card_id, 'rankup' if idolized else 'normal')
def live_download_url(sub_url):
	return 'http://c.dash.moe/live/{0}'.format(sub_url)
# Path function for saving downloaded resources and HTML image embedding
def icon_path(card_id, idolized, local=False):
	if local:
		return 'assets/icon/icon_{0}{1}.png'.format(card_id, '_t'*idolized)
	else:
		return 'http://gitcdn.xyz/repo/iebb/SIFStatic/master/icon/{0}/{1}.png'.format('rankup' if idolized else 'normal', card_id)
def gem_path(name, local=False):
	if local or name in ['void', 'empty', 'placeholder']:
		return 'assets/gem/{0}.png'.format(name)
	else:
		cost, idx = gem_skill_dict[name]['cost'], gem_skill_id_rev_dict[name]
		return 'http://my.llsif.win/images/sis/sis{0}_{1}.png'.format(str(idx).zfill(3), str(cost).zfill(2))
def misc_path(name):
	return 'assets/misc/{0}.png'.format(name)
def live_path(sub_dir, local=False):
	if local:
		return 'assets/live/{0}'.format(sub_dir)
	else:
		return 'https://r.llsif.win/livejson/{0}'.format(sub_dir)

if not Path(card_archive_dir).exists():
	print('{0} does not exist'.format(card_archive_dir))
if not Path(live_archive_dir).exists():
	print('{0} does not exist'.format(live_archive_dir))
if not Path(unit_db_dir).exists():
	print('{0} does not exist'.format(unit_db_dir))
if not Path('assets').is_dir():
	os.mkdir('assets')
	os.mkdir('assets/icon')
	os.mkdir('assets/live')
