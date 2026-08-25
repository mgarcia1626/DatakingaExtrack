lines = open('main_dashboard.py', encoding='utf-8').readlines()
for i, l in enumerate(lines):
    if 'label_visibility' in l and 'collapsed' in l and 'radio' not in l:
        lines[i] = '    label_visibility=' + chr(34) + 'collapsed' + chr(34) + ',\n'
        lines.insert(i + 1, '    key=' + chr(34) + 'menu_principal' + chr(34) + '\n')
        print('inserted at', i+2)
        break
open('main_dashboard.py', 'w', encoding='utf-8').write(''.join(lines))
print('done:', len(lines))
