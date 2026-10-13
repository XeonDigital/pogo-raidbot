# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/XeonDigital/pogo-raidbot/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                     |    Stmts |     Miss |   Cover |   Missing |
|----------------------------------------- | -------: | -------: | ------: | --------: |
| classes/pokedex.py                       |      103 |       61 |     41% |15-17, 21-32, 36-45, 48, 51, 99-100, 116-136, 139-158, 162-163 |
| data/.formats.py                         |       14 |        0 |    100% |           |
| data/pokemon.py                          |        7 |        0 |    100% |           |
| formats.py                               |       63 |       63 |      0% |     2-114 |
| handlers/events/\_\_init\_\_.py          |        4 |        0 |    100% |           |
| handlers/events/deletions.py             |       54 |       37 |     31% |11-30, 33-47, 50-65 |
| handlers/events/interactions.py          |       24 |       19 |     21% |13-15, 27-46 |
| handlers/events/messages.py              |       30 |       23 |     23% |     10-43 |
| handlers/events/reactions.py             |       81 |       70 |     14% |11-24, 27-47, 60-113 |
| handlers/events/slash\_logging.py        |       45 |        0 |    100% |           |
| handlers/friend\_code\_handler.py        |      155 |      125 |     19% |29-44, 62-75, 78-87, 91-97, 100-118, 132-145, 148-171, 188-201, 206-227, 230-269 |
| handlers/helpers.py                      |        8 |        5 |     38% |      6-10 |
| handlers/pokebattler/api\_helper.py      |       90 |       62 |     31% |12-29, 34-40, 43-44, 78-84, 105, 111-143, 146-148 |
| handlers/pokebattler/pokebattler\_api.py |       42 |       21 |     50% |11-16, 19-20, 23-24, 27-28, 56, 63-70, 73 |
| handlers/pokebattler/pokemon\_images.py  |       49 |       16 |     67% |16-22, 36-37, 44-46, 63-66 |
| handlers/pokebattler/pokemon\_lookup.py  |      148 |       13 |     91% |62, 97, 119, 130, 258-272, 309 |
| handlers/raid\_handler.py                |      214 |      170 |     21% |19-21, 37-38, 45-62, 70-81, 88, 94-97, 102-104, 122-125, 128-134, 161-191, 198-209, 213-338 |
| handlers/raid\_lobby\_handler.py         |      477 |      374 |     22% |13-16, 19-27, 34-45, 52, 56-79, 85-101, 109, 112-141, 144, 160-161, 174-256, 264-265, 270-300, 308, 316-324, 336-344, 348-352, 364-374, 377-379, 382-408, 414, 417-434, 440, 451, 461-476, 486, 494, 497-530, 536, 545, 559-561, 571-573, 576-578, 581-603, 607-626, 632, 638, 644-648, 654, 660, 666, 674, 677-685, 706-707, 711-714, 721-757 |
| handlers/raid\_lobby\_management.py      |      150 |       80 |     47% |10-23, 40-41, 58-59, 63-64, 73, 90-91, 109, 115-128, 136-185, 188-192, 200, 210, 215-221 |
| handlers/request\_handler.py             |      285 |      247 |     13% |14-25, 31-32, 38-41, 53-68, 77, 83-86, 92-95, 102-137, 149-171, 174-181, 184-214, 217-252, 259-273, 276-278, 282-323, 326-338, 342-344, 348-365, 369-386 |
| handlers/startup\_handler.py             |      141 |      104 |     26% |13-19, 26-82, 88-89, 98-108, 112-117, 123-129, 135, 147-152, 161, 163, 166-207 |
| handlers/sticky\_handler.py              |       81 |       65 |     20% |11-14, 20-35, 42, 52-53, 56-62, 65-71, 74-77, 80-83, 86-89, 92-119 |
| init\_database.py                        |       33 |       33 |      0% |     1-182 |
| main.py                                  |       42 |       42 |      0% |      3-64 |
| pogo\_raid\_lib.py                       |      316 |      130 |     59% |34, 47-48, 66-67, 90-92, 98-99, 127-128, 134, 189-190, 198-217, 221-248, 252-262, 331-351, 354, 359-377, 380, 386-396, 399, 425, 436-450, 453-463 |
| tasks.py                                 |       61 |       61 |      0% |      4-88 |
| **TOTAL**                                | **2717** | **1821** | **33%** |           |


## Setup coverage badge

Below are examples of the badges you can use in your main branch `README` file.

### Direct image

[![Coverage badge](https://raw.githubusercontent.com/XeonDigital/pogo-raidbot/python-coverage-comment-action-data/badge.svg)](https://htmlpreview.github.io/?https://github.com/XeonDigital/pogo-raidbot/blob/python-coverage-comment-action-data/htmlcov/index.html)

This is the one to use if your repository is private or if you don't want to customize anything.

### [Shields.io](https://shields.io) Json Endpoint

[![Coverage badge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/XeonDigital/pogo-raidbot/python-coverage-comment-action-data/endpoint.json)](https://htmlpreview.github.io/?https://github.com/XeonDigital/pogo-raidbot/blob/python-coverage-comment-action-data/htmlcov/index.html)

Using this one will allow you to [customize](https://shields.io/endpoint) the look of your badge.
It won't work with private repositories. It won't be refreshed more than once per five minutes.

### [Shields.io](https://shields.io) Dynamic Badge

[![Coverage badge](https://img.shields.io/badge/dynamic/json?color=brightgreen&label=coverage&query=%24.message&url=https%3A%2F%2Fraw.githubusercontent.com%2FXeonDigital%2Fpogo-raidbot%2Fpython-coverage-comment-action-data%2Fendpoint.json)](https://htmlpreview.github.io/?https://github.com/XeonDigital/pogo-raidbot/blob/python-coverage-comment-action-data/htmlcov/index.html)

This one will always be the same color. It won't work for private repos. I'm not even sure why we included it.

## What is that?

This branch is part of the
[python-coverage-comment-action](https://github.com/marketplace/actions/python-coverage-comment)
GitHub Action. All the files in this branch are automatically generated and may be
overwritten at any moment.