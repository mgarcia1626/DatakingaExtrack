lines = open('main_dashboard.py', encoding='utf-8').readlines()
clean = lines[:260] + lines[306:]
open('main_dashboard.py', 'w', encoding='utf-8').write(''.join(clean))
print('Done:', len(clean), 'lines')
