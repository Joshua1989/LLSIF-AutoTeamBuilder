# LLSIF-AutoTeamBuilder
Automatically build the optimal team according to given live and user profile

![](https://github.com/Joshua1989/LLSIF-AutoTeamBuilder/blob/master/demo%20images/optimal_team.png)

## Dependencies
Enviroment: Python3 & Jupyter notebook

Modules: `pandas, numpy, beautifulsoup4, json, sqlite3`

## Features
* Import user profile from tshark json packets or [ieb Stats site](http://stats.llsif.win/)
* Provide format converter for [LL组卡器](https://tieba.baidu.com/p/4986384618), [LL Helper](http://llhelper.duapp.com/), and [ieb Stats site](http://stats.llsif.win/)
* HTML view of all objects under Jupyter environment
* Customize selecting and sorting for user cards
  ![](https://github.com/Joshua1989/LLSIF-AutoTeamBuilder/blob/master/demo%20images/custom_query.png)
* Built-in simulator to with comprehensive stats
  ![](https://github.com/Joshua1989/LLSIF-AutoTeamBuilder/blob/master/demo%20images/simulator_stats.png)
  ![](https://github.com/Joshua1989/LLSIF-AutoTeamBuilder/blob/master/demo%20images/simulation_details.png)

## Documents
Notice most image and live resources are scraped after installation, the documents below are not displayed correctly in Github.

* Tutorial.ipynb: A general guide for how to use the module `llatb` and how to build optimal team
* doc folder: Advanded theoretic material and algorithm details.
