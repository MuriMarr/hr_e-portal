from flask import Flask, render_template, redirect, url_for, request, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime as dt, timedelta
import pdfkit
from flask import make_response
from werkzeug.utils import secure_filename
import os

CHAVE_SECRETA_ADMIN = 'admin@1234'

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sua-chave-secreta-aqui'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

# Modelo de usuário
from datetime import date
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha = db.Column(db.String(200), nullable=False)
    tipo = db.Column(db.String(20), default='funcionario')  # funcionario ou admin
    ativo = db.Column(db.Boolean, default=True)  # Se o usuário está ativo
    salario_mensal = db.Column(db.Float, default=1940.00)  # Salário mensal padrão
    cpf = db.Column(db.String(14), nullable=True)  # CPF do funcionário
    data_admissao = db.Column(db.Date, default=date.today) # Data de admissão
    data_demissao = db.Column(db.Date)  # Data de demissão, se aplicável

from datetime import datetime
class Aviso(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(100), nullable=False)
    conteudo = db.Column(db.Text, nullable=False)
    imagem = db.Column(db.String(150))
    criado_em = db.Column(db.DateTime, default=datetime.datetime.utcnow)

# Carregar usuário pelo ID (requerido pelo Flask-Login)
@login_manager.user_loader
def carregar_usuario(user_id):
    return User.query.get(int(user_id))

# Injetar data e hora atual nas templates
from datetime import datetime
@app.context_processor
def inject_now():
    return {'now': datetime.now}

# Página inicial / dashboard
@app.route('/')
@login_required
def dashboard():
    return render_template('dashboard.html', nome=current_user.nome, tipo=current_user.tipo)

# Página de administração (apenas para admin)
@app.route('/criar_admin', methods=['GET', 'POST'])
def criar_login():
        from werkzeug.security import generate_password_hash

        existente = User.query.filter_by(email='admin@gmail.com').first()
        if existente:
            flash('Administrador já existe.', 'warning')
            return redirect(url_for('login'))
        
        admin = User(nome='Administrador', email='admin@gmail.com', senha=generate_password_hash('admin123'), tipo='admin')
        db.session.add(admin)
        db.session.commit()
        return 'Administrador criado com sucesso.'

@app.route('/admin')
@login_required
def admin():
    if current_user.tipo != 'admin':
        abort(403)

    funcionarios = User.query.filter_by(tipo='funcionario').all()
    return render_template('admin/admin.html', funcionario=funcionarios)

@app.route('/admin/cadastrar_admin', methods=['GET', 'POST'])
@login_required
def cadastrar_admin():
    if current_user.tipo != 'admin':
        abort(403)

    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        senha = request.form['senha']
        tipo = request.form['tipo']

        if User.query.filter_by(email=email).first():
            flash('Email já cadastrado.', 'warning')
            return redirect(url_for('cadastrar_admin'))
        
        novo_usuario = User(nome=nome, email=email, senha=generate_password_hash(senha), tipo=tipo)
        db.session.add(novo_usuario)
        db.session.commit()
        flash(f'{tipo.capitalize()} cadastrado com sucesso.', 'success')
        return redirect(url_for('admin'))

    return render_template('admin/cadastrar_admin.html')

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.tipo != 'admin':
        abort(403)

    total_funcionarios = User.query.filter_by(tipo='funcionario').count()
    total_registros = Ponto.query.count()

    hoje = datetime.today()
    ano, mes = hoje.year, hoje.month
    registros = Ponto.query.filter(Ponto.data.startswith(f"{ano}-{mes:02d}")).all()

    total_horas = timedelta()

    for r in registros:
        if r.hora_entrada and r.hora_saida:
            entrada = dt.strptime(r.hora_entrada, "%H:%M:%S")
            saida = dt.strptime(r.hora_saida, "%H:%M:%S")
            total_horas += (saida - entrada)
    horas_formatadas = round(total_horas.total_seconds() / 3600, 2)

    return render_template('admin/admin_dashboard.html', total_funcionarios=total_funcionarios, total_registros=total_registros, total_horas=horas_formatadas)

@app.route('/admin/avisos/criar', methods=['GET', 'POST'])
@login_required
def criar_aviso():
    if current_user.tipo != 'admin':
        abort(403)

    if request.method == 'POST':
        titulo = request.form['titulo']
        conteudo = request.form['conteudo']
        imagem = request.files.get('imagem')

        nome_arquivo = None
        if imagem and imagem.filename != '':
            nome_arquivo = secure_filename(imagem.filename)
            caminho = os.path.join(app.config['UPLOAD_FOLDER'], nome_arquivo)
            imagem.save(caminho)

        aviso = Aviso(titulo=titulo, conteudo=conteudo, imagem=nome_arquivo)
        db.session.add(aviso)
        db.session.commit()
        flash('Aviso criado com sucesso.', 'success')
        return redirect(url_for('listar_avisos_admin'))
    
    return render_template('admin/form_aviso.html')

@app.route('/avisos')
@login_required
def mural():
    avisos = Aviso.query.order_by(Aviso.data_publicacao.desc()).all()
    return render_template('mural.html', avisos=avisos)

@app.route('/admin/avisos/novo', methods=['GET', 'POST'])
@login_required
def novo_aviso():
    if current_user.tipo != 'admin':
        abort(403)

    if request.method == 'POST':
        titulo = request.form['titulo']
        conteudo = request.form['conteudo']
        imagem = request.form.get('imagem', '')

        aviso = Aviso(titulo=titulo, conteudo=conteudo, imagem=imagem)
        db.session.add(aviso)
        db.session.commit()
        flash('Aviso publicado com sucesso!', 'success')
        return redirect(url_for('mural'))
    
    return render_template('admin/novo_aviso.html')

@app.route('/admin/cadastrar_funcionario', methods=['GET', 'POST'])
@login_required
def cadastrar_funcionario():
    if current_user.tipo != 'admin':
        abort(403)

    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        senha = request.form['senha']
        tipo = request.form['tipo']

        if User.query.filter_by(email=email).first():
            flash('Email já cadastrado.', 'warning')
            return redirect(url_for('cadastrar_funcionario'))
        
        novo_funcionario = User(nome=nome, email=email, senha=generate_password_hash(senha), tipo=tipo)
        db.session.add(novo_funcionario)
        db.session.commit()
        flash(f'{tipo.capitalize()} cadastrado com sucesso.', 'success')
        return redirect(url_for('funcionarios'))
    
    return render_template('admin/cadastrar_funcionario.html')

@app.route('/admin/funcionario/<int:id>/desligar', methods=['GET', 'POST'])
@login_required
def desligar_funcionario(id):
    if current_user.tipo != 'admin':
        abort(403)

    funcionario = User.query.get_or_404(id)
    registros = Ponto.query.filter_by(user_id=funcionario.id).all()

    from datetime import datetime, timedelta

    total_horas = timedelta()
    for r in registros:
        if r.hora_entrada and r.hora_saida:
            entrada = datetime.strptime(r.hora_entrada, "%H:%M:%S")
            saida = datetime.strptime(r.hora_saida, "%H:%M:%S")
            total_horas += (saida - entrada)
    
    # Geração do TRCT com valores
    salario_base = 1940.00
    horas_trabalhadas = total_horas.total_seconds() / 3600
    valor_hora = salario_base / (22 * 10)
    valor_trct = round(horas_trabalhadas * valor_hora, 2)

    if request.method == 'POST':
        funcionario.ativo = False
        funcionario.data_demissao = datetime.today().date()
        db.session.commit()
        flash(f'Funcionário {funcionario.nome} desligado. Valor do TRCT: R$ {valor_trct}', 'success')
        return redirect(url_for('funcionarios'))
    
    return render_template('admin/desligar_funcionario.html', funcionario=funcionario, total_horas=round(horas_trabalhadas, 2), valor=valor_trct)

def calcular_trct(funcionario, data_demissao):
    salario_base = funcionario.salario_mensal
    admissao = funcionario.data_admissao
    demissao = data_demissao

    # 1. Saldo de salário
    dias_trabalhados = demissao.day
    saldo_salario = round((salario_base / 30) * dias_trabalhados, 2)

    # 2. Férias vencidas + 1/3
    ferias_vencidas = round(salario_base + (salario_base / 3), 2)

    # 3. Férias proporcionais + 1/3
    meses_trabalhados = (demissao.year - admissao.year) * 12 + (demissao.month - admissao.month)
    ferias_proporcionais = round(((salario_base / 12) * meses_trabalhados) + (((salario_base / 12) * meses_trabalhados) / 3), 2)

    # 4. 13º salário proporcional
    decimo_terceiro = round((salario_base / 12) * data_demissao.month, 2)

    # 5. Multa do FGTS
    total_fgts = round((salario_base * 0.08) * meses_trabalhados, 2)  # Considerando 8% de FGTS
    multa_fgts = round(total_fgts * 0.4, 2)  # 40% de multa sobre o FGTS

    # 6. Descontos
    desconto_inss = round(salario_base * 0.08, 2)  # 8% de INSS
    desconto_vt = round(salario_base * 0.05, 2)  # 5% de vale transporte

    # 7. Total do TRCT
    total_liquido = round(saldo_salario + ferias_vencidas + ferias_proporcionais + decimo_terceiro + multa_fgts - desconto_inss - desconto_vt, 2)
    return {
        'admissao': admissao.strftime('%d/%m/%Y'),
        'demissao': demissao.strftime('%d/%m/%Y'),
        'motivo_rescisao': "Sem justa causa",
        'saldo_salario': saldo_salario,
        'ferias_vencidas': ferias_vencidas,
        'ferias_proporcionais': ferias_proporcionais,
        'decimo_terceiro': decimo_terceiro,
        'multa_fgts': multa_fgts,
        'desconto_inss': desconto_inss,
        'desconto_vt': desconto_vt,
        'total_liquido': total_liquido
    }

import pdfkit
@app.route('/admin/funcionario/<int:id>/trct_pdf')
@login_required
def gerar_trct(id):
    if current_user.tipo != 'admin':
        abort(403)

    funcionario = User.query.get_or_404(id)

    if not funcionario.data_demissao:
        flash('Funcionário ainda não foi desligado.', 'warning')
        return redirect(url_for('funcionarios'))

    trct = calcular_trct(funcionario, funcionario.data_demissao)

    rendered_html = render_template("trct_pdf.html", funcionario=funcionario, trct=trct)

    config = pdfkit.configuration(wkhtmltopdf=r'C:/Arquivos de Programas/wkhtmltopdf/bin/wkhtmltopdf.exe')
    pdf = pdfkit.from_string(rendered_html, False, configuration=config)

    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=TRCT_{funcionario.nome}.pdf'
    return response

# Página de login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.tipo == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
       
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.senha, senha):
            login_user(user)
            if user.tipo == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('dashboard'))
        else:
            flash('E-Mail ou senha incorretos.', 'danger')

    return render_template('login.html')

# Logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

class Ponto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    data = db.Column(db.String(10))
    hora_entrada = db.Column(db.String(8))
    hora_saida = db.Column(db.String(8))

# Página de registro
@app.route('/registrar_funcionario', methods=['GET', 'POST'])
def registrar_funcionario():
    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        senha = request.form['senha']
        tipo = request.form.get('tipo', 'funcionario')
        chave_admin = request.form.get('chave_admin', '')
        
        if User.query.filter_by(email=email).first():
            flash('Email já cadastrado.', 'warning')
            return redirect(url_for('registrar_funcionario'))
        
        if tipo == 'admin':
            if chave_admin != 'CHAVE_SECRETA_ADMIN':
                flash('Chave de autenticação inválida para administrador.', 'danger')
                return redirect(url_for('registrar_funcionario'))
        
        novo_user = User(nome=nome, email=email, senha=generate_password_hash(senha), tipo=tipo, ativo=True)
        db.session.add(novo_user)
        db.session.commit()
        flash('Cadastro realizado com sucesso. Faça login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/registrar_entrada')
@login_required
def registrar_entrada():
    hoje = datetime.now().strftime("%d-%m-%Y")
    hora = datetime.now().strftime("%H:%M:%S")
    
    # Verificação de entradas ou saídas existentes
    ponto = Ponto(user_id=current_user.id, data=hoje, hora_entrada=hora)
    if ponto:
        flash('Você já registrou sua entrada hoje.', 'warning')
    else:
        novo_ponto = ponto(user_id=current_user.id, data=hoje, hora_entrada=hora)
        db.session.add(novo_ponto)
        db.session.commit()
        flash('Entrada registrada às {hora}.', 'success')
    
    if not current_user.ativo:
        flash('Usuário desligado não pode registrar ponto.', 'danger')
    
    return redirect(url_for('dashboard'))

@app.route('/registrar_saida')
@login_required
def registrar_saida():
    hoje = datetime.now().strftime("%d-%m-%Y")
    hora = datetime.now().strftime("%H:%M:%S")
    
    ponto = Ponto.query.filter_by(user_id=current_user.id, data=hoje, hora_saida=None).first()
    if ponto:
        ponto.hora_saida = hora
        db.session.commit()
        flash('Saída registrada às {hora}.', 'success')
    else:
        flash('Você não registrou sua entrada ou já registrou sua saída hoje.', 'warning')

    if not current_user.ativo:
        flash('Usuário desligado não pode registrar ponto.', 'danger')
    
    return redirect(url_for('dashboard'))

@app.route('/historico')
@login_required
def historico():
    # Parâmetros do GET
    mes_param = request.args.get('mes')
    hoje = datetime.today()
    if mes_param:
        try:
            ano, mes = map(int, mes_param.split('-'))
            mes_display = f"{ano}-{mes:02d}"
        except:
            ano, mes = hoje.year, hoje.month
            mes_display = hoje.strftime("%m-%Y")
    else:
        ano, mes = hoje.year, hoje.month
        mes_display = hoje.strftime("%m-%Y")

    registros = Ponto.query.filter(Ponto.user_id == current_user.id, Ponto.data.startswith(f"{ano}-{mes:02d}")).order_by(Ponto.data.desc()).all()
    
    jornada_padrao = timedelta(hours=10)
    historico_calculado = []
    saldo_total = timedelta()

    for r in registros:
        entrada = datetime.strptime(r.hora_entrada, "%H:%M:%S") if r.hora_entrada else None
        saida = datetime.strptime(r.hora_saida, "%H:%M:%S") if r.hora_saida else None
        data = r.data

        if entrada and saida:
            horas_trabalhadas = saida - entrada
            saldo_dia = horas_trabalhadas - jornada_padrao
            saldo_total += saldo_dia
        else:
            horas_trabalhadas = None
            saldo_dia = None
        
        historico_calculado.append({
            'data': data,
            'entrada': r.hora_entrada,
            'saida': r.hora_saida,
            'horas_trabalhadas': str(horas_trabalhadas) if horas_trabalhadas else '—',
            'saldo': str(saldo_dia) if saldo_dia else '—'
        })

    return render_template('historico.html', registros=historico_calculado, saldo_total=str(saldo_total), mes_atual=mes_display)

@app.route('/holerite')
@login_required
def gerar_holerite():
    from datetime import datetime, timedelta

    mes_param = request.args.get('mes')
    hoje = datetime.today()
    ano, mes = hoje.year, hoje.month

    if mes_param:
        try:
            ano, mes = map(int, mes_param.split('-'))
        except:
            pass
        
    mes_display = f"{ano}-{mes:02d}"
        
    registros = Ponto.query.filter(Ponto.user_id == current_user.id, Ponto.data.startswith(f"{ano}-{mes:02d}")).order_by(Ponto.data.desc()).all()
    
    jornada_padrao = timedelta(hours=10)
    total_trabalhado = timedelta()
    dias_trabalhados = 0

    for r in registros:
        if r.hora_entrada and r.hora_saida:
            entrada = datetime.strptime(r.hora_entrada, "%H:%M:%S")
            saida = datetime.strptime(r.hora_saida, "%H:%M:%S")
            total_trabalhado += (saida - entrada)
            dias_trabalhados += 1

    salario_base = 1940.00 # Salário base
    valor_hora = salario_base / (jornada_padrao.total_seconds() / 3600 * 22)
    horas_trabalhadas = total_trabalhado.total_seconds() / 3600
    salario_total = round(valor_hora * horas_trabalhadas, 2)

    
    rendered_html = render_template("holerite.html", nome=current_user.nome, mes=mes_display, dias=dias_trabalhados, horas=round(horas_trabalhadas, 2), salario=salario_total)
    
    config = pdfkit.configuration(wkhtmltopdf=r'C:/Arquivos de Programas/wkhtmltopdf/bin/wkhtmltopdf.exe')
    pdf = pdfkit.from_string(rendered_html, False, configuration=config)
    
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=holerite_{mes_display}.pdf'
    return response

@app.route('/admin/funcionarios')
@login_required
def funcionarios():
    if current_user.tipo != 'admin':
        abort(403)

    lista = User.query.filter(User.tipo == 'funcionario').order_by(User.data_demissao.isnot(None), User.nome).all()
    return render_template('admin/admin_funcionario.html', funcionarios=lista)

@app.route('/admin/funcionario/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_funcionario(id):
    if current_user.tipo != 'admin':
        abort(403)

    funcionario = User.query.get_or_404(id)

    if request.method == 'POST':
        funcionario.nome = request.form['nome']
        funcionario.email = request.form['email']
        db.session.commit()
        flash('Funcionário atualizado com sucesso.', 'success')
        return redirect(url_for('funcionarios'))
    
    return render_template('admin/editar_funcionario.html', funcionario=funcionario)

@app.route('/admin/funcionario/<int:id>/excluir')
@login_required
def excluir_funcionario(id):
    if current_user.tipo != 'admin':
        abort(403)

    funcionario = User.query.get_or_404(id)
    db.session.delete(funcionario)
    db.session.commit()
    flash('Funcionário excluído com sucesso.', 'success')
    return redirect(url_for('funcionarios'))
    
@app.route('/admin/funcionario/<int:id>/historico')
@login_required
def historico_funcionario(id):
    if current_user.tipo != 'admin':
        abort(403)

    user = User.query.get_or_404(id)
    mes_param = request.args.get('mes')

    hoje = datetime.today()
    ano, mes = hoje.year, hoje.month
    if mes_param:
        try:
            ano, mes = map(int, mes_param.split('-'))
        except:
            pass

    registros = Ponto.query.filter(Ponto.user_id == user.id, Ponto.data.startswith(f"{ano}-{mes:02d}")).order_by(Ponto.data).all()

    jornada_padrao = timedelta(hours=10)
    saldo_total = timedelta()
    lista = []
    for r in registros:
        ent = datetime.strptime(r.hora_entrada, "%H:%M:%S") if r.hora_entrada else None
        sai = datetime.strptime(r.hora_saida, "%H:%M:%S") if r.hora_saida else None
        data = r.data

        if ent and sai:
            trabalhadas = sai - ent
            saldo = trabalhadas - jornada_padrao
            saldo_total += saldo
        else:
            trabalhadas = None
            saldo = None

        lista.append({
            'data': data,
            'entrada': r.hora_entrada,
            'saida': r.hora_saida,
            'horas_trabalhadas': str(trabalhadas) if trabalhadas else '—',
            'saldo': str(saldo) if saldo else '—'
        })

    return render_template('historico_funcionario.html', nome=user.nome, registros=lista, saldo_total=str(saldo_total), mes_atual=f"{ano}-{mes:02d}", id=user.id)

@app.route('/admin/funcionario/<int:id>/holerite')
@login_required
def holerite_funcionario(id):
    if current_user.tipo != 'admin':
        abort(403)

    user = User.query.get_or_404(id)
    mes_param = request.args.get('mes')
    from datetime import datetime, timedelta

    hoje = datetime.today()
    ano, mes = hoje.year, hoje.month
    if mes_param:
        try:
            ano, mes = map(int, mes_param.split('-'))
        except:
            pass

    registros = Ponto.query.filter(Ponto.user_id == user.id, Ponto.data.startswith(f"{ano}-{mes:02d}")).all()

    jornada = timedelta(hours=10)
    total = timedelta()
    extras = timedelta()
    dias_trabalhados = 0

    for r in registros:
        if r.hora_entrada and r.hora_saida:
            ent = datetime.strptime(r.hora_entrada, "%H:%M:%S")
            sai = datetime.strptime(r.hora_saida, "%H:%M:%S")
            trabalhadas = sai - ent
            total += trabalhadas
            dias_trabalhados += 1

            if trabalhadas > jornada:
                extras += (trabalhadas - jornada)

    # Cálculo do salário
    salario_base = 1940.00
    horas_trabalhadas = total.total_seconds() / 3600 # Total de horas trabalhadas
    horas_extras = extras.total_seconds() / 3600 # Total de horas extras

    valor_hora = salario_base / (22 * 10)  # 22 dias úteis, 10 horas por dia
    valor_base = round(horas_trabalhadas * valor_hora, 2) # Salário base
    valor_extras = round(horas_extras * valor_hora * 1.5, 2)  # 50% a mais para horas extras
    bruto = valor_base + valor_extras

    desconto_inss = round(bruto * 0.08, 2)  # 8% de INSS
    desconto_vt = round(bruto * 0.05, 2)  # 5% de vale transporte
    liquido = round(bruto - desconto_inss - desconto_vt, 2) # Salário líquido 

    rendered_html = render_template("holerite.html", nome=user.nome, mes=f"{ano}-{mes:02d}", dias=dias_trabalhados, horas=round(horas_trabalhadas, 2), salario_base=salario_base, valor_base=valor_base, valor_extras=valor_extras, bruto=bruto, desconto_inss=desconto_inss, desconto_vt=desconto_vt, valor_liquido=liquido)

    import pdfkit
    
    config = pdfkit.configuration(wkhtmltopdf=r'C:/Arquivos de Programas/wkhtmltopdf/bin/wkhtmltopdf.exe')
    pdf = pdfkit.from_string(rendered_html, False, configuration=config)
   
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=holerite_{user.nome}.pdf'
    return response

# Rodar o app
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)