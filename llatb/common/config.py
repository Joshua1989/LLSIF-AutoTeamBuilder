import os
from pathlib import Path

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
def icon_path(card_id, idolized):
	return 'assets/icon/icon_{0}{1}.png'.format(card_id, '_t'*idolized)
def gem_path(name):
	return 'assets/gem/{0}.png'.format(name)
def misc_path(name):
	return 'assets/misc/{0}.png'.format(name)
def live_path(sub_dir):
	return 'assets/live/{0}'.format(sub_dir)

if not Path(card_archive_dir).exists():
	print('{0} does not exist'.format(card_archive_dir))
if not Path(unit_db_dir).exists():
	print('{0} does not exist'.format(unit_db_dir))
if not Path('assets').is_dir():
	os.mkdir('assets')
	os.mkdir('assets/icon')
	os.mkdir('assets/live')
