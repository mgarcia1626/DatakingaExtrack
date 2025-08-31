# Requiere: pip install requests beautifulsoup4
import requests
from bs4 import BeautifulSoup

session = requests.Session()
login_url = 'https://datakinga.com/Login.aspx?ReturnUrl=%2fVerCintaTestigo.aspx'
data_url = 'https://datakinga.com/VerCintaTestigo.aspx'

# 1. LOGIN
login_page = session.get(login_url)
soup = BeautifulSoup(login_page.text, 'html.parser')
viewstate = soup.find('input', {'name': '__VIEWSTATE'})['value']
eventvalidation = soup.find('input', {'name': '__EVENTVALIDATION'})['value']
viewstategenerator = soup.find('input', {'name': '__VIEWSTATEGENERATOR'})['value']

# Completa tus credenciales aquí
usuario = 'Datakinga'
clave = 'sol1234'

payload_login = {
    '__VIEWSTATE': viewstate,
    '__EVENTVALIDATION': eventvalidation,
    '__VIEWSTATEGENERATOR': viewstategenerator,
    'txtUsuario': usuario,
    'txtClave': clave,
    '__EVENTTARGET': 'Ingresar',
    '__EVENTARGUMENT': ''
}

response_login = session.post(login_url, data=payload_login)

# 2. PROCESAR (simular clic en "Procesar")
data_page = session.get(data_url)
soup = BeautifulSoup(data_page.text, 'html.parser')
viewstate = soup.find('input', {'name': '__VIEWSTATE'})['value']
eventvalidation = soup.find('input', {'name': '__EVENTVALIDATION'})['value']
viewstategenerator = soup.find('input', {'name': '__VIEWSTATEGENERATOR'})['value']

payload_procesar = {
    '__VIEWSTATE': viewstate,
    '__EVENTVALIDATION': eventvalidation,
    '__VIEWSTATEGENERATOR': viewstategenerator,
    '__EVENTTARGET': '',
    '__EVENTARGUMENT': '',
    'ctl00$ContentPlaceHolder1$txtDesde': '23/08/2025',
    'ctl00$ContentPlaceHolder1$txtHasta': '23/08/2025',
    'ctl00$ContentPlaceHolder1$chkSucursales$0': 'on',
    'ctl00$ContentPlaceHolder1$chkSucursales$1': 'on',
    'ctl00$ContentPlaceHolder1$chkSucursales$2': 'on',
    'ctl00$ContentPlaceHolder1$chkSucursales$3': 'on',
    'ctl00$ContentPlaceHolder1$chkSucursales$4': 'on',
    'ctl00$ContentPlaceHolder1$chkTurnos$0': 'on',
    'ctl00$ContentPlaceHolder1$chkTurnos$1': 'on',
    'ctl00$ContentPlaceHolder1$chkTurnos$2': 'on',
    'ctl00$ContentPlaceHolder1$cmbMozo': 'Todos',
    'ctl00$ContentPlaceHolder1$cmbMesa': 'Todas',
    'ctl00$ContentPlaceHolder1$cmdProcesar': 'Procesar'
}

response_procesar = session.post(data_url, data=payload_procesar)

# Guarda la respuesta HTML para revisar el resultado de "Procesar"
with open('procesar_result.html', 'w', encoding='utf-8') as f:
    f.write(response_procesar.text)

print("Archivo 'procesar_result.html' generado. Ábrelo en tu navegador para ver el resultado.")
