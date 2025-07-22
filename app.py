from flask import Flask, render_template, redirect, url_for, request, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sua-chave-secreta-aqui'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

# Modelo de usuário
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha = db.Column(db.String(200), nullable=False)
    tipo = db.Column(db.String(20), default='funcionario')  # funcionario ou admin

# Carregar usuário pelo ID (requerido pelo Flask-Login)
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Página inicial / dashboard
@app.route('/')
@login_required
def dashboard():
    return render_template('dashboard.html', nome=current_user.nome, tipo=current_user.tipo)

# Página de administração (apenas para admin)
@app.route('/admin')
@login_required
def admin():
    if current_user.tipo != 'admin':
        abort(403)

    funcionarios = User.query.filter_by(tipo='funcionario').all()
    return render_template('template-admin.html', funcionarios=funcionarios)
@app.route('/admin/cadastrar', methods=['GET', 'POST'])
@login_required
def cadastrar_funcionario():
    if current_user.tipo != 'admin':
        abort(403)

    if request.method == "POST":
        nome = request.form['nome']
        email = request.form['email']
        senha = request.form['senha']

        if User.query.filter_by(email=email).first():
            flash('Email já cadastrado.', 'warning')
            return redirect(url_for('cadastrar_funcionario'))
        
        senha_hash = generate_password_hash(senha)
        novo_funcionario = User(nome=nome, email=email, senha=senha_hash, tipo='funcionario')
        db.session.add(novo_funcionario)
        db.session.commit()
        flash('Funcionário cadastrado com sucesso.', 'success')
        return redirect(url_for('admin'))
    
    return render_template('cadastrar-funcionario.html')

# Página de login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.senha, senha):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Email ou senha incorretos.', 'danger')
    
    return render_template('login.html')

# Página de registro
@app.route('/registrar_funcionario', methods=['GET', 'POST'])
def registrar_funcionario():
    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        senha = request.form['senha']
        
        if User.query.filter_by(email=email).first():
            flash('Email já cadastrado.', 'warning')
            return redirect(url_for('registrar_funcionario'))

        nova_senha = generate_password_hash(senha)
        novo_user = User(nome=nome, email=email, senha=nova_senha)
        db.session.add(novo_user)
        db.session.commit()
        flash('Cadastro realizado com sucesso. Faça login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

# Logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

from datetime import datetime

class Ponto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    data = db.Column(db.String(10))
    hora_entrada = db.Column(db.String(8))
    hora_saida = db.Column(db.String(8))

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

    return redirect(url_for('dashboard'))

@app.route('/historico')
@login_required
def historico():
    from datetime import datetime, timedelta
    
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

import pdfkit
from flask import make_response

@app.route('/holerite')
@login_required
def gerar_holerite():
    from datetime import datetime, timedelta

    mes_param = request.args.get('mes')
    hoje = datetime.today()

    if mes_param:
        try:
            ano, mes = map(int, mes_param.split('-'))
            mes_display = f"{ano}-{mes:02d}"
        except:
            ano, mes = hoje.month, hoje.year
            mes_display = hoje.strftime("%m-%Y")
        else:
            ano, mes = hoje.year, hoje.month
            mes_display = hoje.strftime("%m-%Y")

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

        salario_base = 1940.00 # Exemplo de salário base
        valor_hora = salario_base / (jornada_padrao.total_seconds() / 3600 * 22)
        horas_trabalhadas = total_trabalhado.total_seconds() / 3600
        salario_total = round(valor_hora * horas_trabalhadas, 2)

        rendered_html = render_template("holerite.html", nome=current_user.nome, mes=mes_display, dias=dias_trabalhados, horas=round(horas_trabalhadas, 2), salario=salario_total())
        pdf = pdfkit.from_string(rendered_html, False)
        
        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=holerite_{mes_display}.pdf'
        return response

# Rodar o app
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
