# 💈 BarberSaaS - Sistema de Gestão para Barbearias com Mercado Pago

SaaS moderno e completo desenvolvido especialmente para barbearias, com controle de valores dinâmicos, comissões de barbeiros, controle de estoque de produtos, fluxo de caixa, agendamento com pagamento antecipado e **Clube de Assinatura Recorrente estilo Netflix / Amazon** via **Mercado Pago Developers**.

---

## 🚀 Como Iniciar o Sistema

### 1. Iniciar a Aplicação
Abra o terminal na pasta do projeto e execute:

```powershell
python run.py
```

O script irá automaticamente:
- Criar e configurar o banco de dados (`barbershop.db`)
- Inserir dados de demonstração da **Barbearia Dom Augusto**
- Subir o servidor web na porta `8000`

### 2. Links de Acesso
- **Painel do Gestor / Dono da Barbearia:** [http://localhost:8000/login](http://localhost:8000/login)
  - **E-mail:** `admin@barbearia.com`
  - **Senha:** `123456`
- **Página Pública do Cliente (Agendamento & Assinatura):** [http://localhost:8000/b/dom-augusto](http://localhost:8000/b/dom-augusto)

---

## 🌟 Funcionalidades Principais

### 1. ✂️ Serviços & Tabela de Preços Dinâmica
- O dono da barbearia configura e edita livremente os valores e tempos estimados de atendimento.
- Exemplos já configurados:
  - **Corte Degradê / Fade:** R$ 45,00 (35 min)
  - **Barba Terapia com Toalha Quente:** R$ 35,00 (30 min)
  - **Sobrancelha na Navalha:** R$ 15,00 (15 min)
  - **Combo Cabelo + Barba Completo:** R$ 75,00 (60 min)
  - **Nevou / Platinado:** R$ 120,00 (90 min)

### 2. 💈 Barbeiros & Comissões Personalizadas
- Cadastro de profissionais com comissões individuais em **Serviços** (%) e **Produtos** (%).
- Cálculo automático das comissões acumuladas a cada corte concluído ou produto vendido.
- Controle de **Ganhos**, **Repasses Já Pagos** e **Saldo Pendente**.
- Botão rápido de **Repassar Comissão** integrado ao fluxo financeiro.

### 3. 👑 Clube de Assinatura Mensal (Estilo Netflix / Amazon Prime)
- O cliente paga um valor fixo por mês (ex: **R$ 89,00/mês**) e tem direito a cortar o cabelo quantas vezes quiser no mês (ou com limite pré-estabelecido).
- Totalmente editável pelo dono da barbearia:
  - Nome do plano (ex: *Clube VIP*, *Clube Black*)
  - Preço da mensalidade
  - Limite de cortes ou ilimitado
  - Benefícios incluídos (ex: *1 Cerveja ou café grátis por visita, 10% off em produtos*)
- Controle de clientes assinantes com contador de cortes utilizados no mês.

### 4. 💳 Pagamentos Seguros com Mercado Pago Developers
- **Zero Risco de Vazamento de Cartão:** Nenhuma informação de cartão de crédito trafega ou fica armazenada no servidor da barbearia. Todo o processo é executado nos servidores certificados **PCI-DSS Nível 1 do Mercado Pago**.
- **Antecipação de Pagamento:** Ao agendar online pelo celular, o cliente pode optar por pagar antecipado com **PIX** ou **Cartão**, garantindo a reserva do horário.
- **Dinheiro Direto na Conta do Dono:** Cada barbearia insere seu próprio `Access Token` nas Configurações, fazendo com que o dinheiro caia direto na conta bancária/Mercado Pago da barbearia.
- **Simulador Interativo Integrado:** Permite testar o fluxo completo de pagamento e assinatura mesmo antes de cadastrar uma chave real do Mercado Pago.

### 5. 🧴 Produtos & Controle de Estoque
- Cadastro de pomadas, óleos, minoxidil e bebidas com preço de custo e venda.
- Alerta visual de estoque baixo.
- **Venda Rápida de Balcão:** Realiza a baixa imediata no estoque, credita a comissão do barbeiro que vendeu e lança a receita no caixa da barbearia.

### 6. 💰 Finanças & Fluxo de Caixa Completo
- Resumo em tempo real de:
  - Faturamento do dia e do mês
  - Despesas operacionais (aluguel, contas, insumos)
  - Comissões pagas e pendentes
  - Lucro Líquido real do negócio
  - Histórico detalhado de movimentações com filtros

---

## 🛠️ Tecnologias Utilizadas
- **Backend:** Python 3.14 + FastAPI + Uvicorn
- **Banco de Dados:** SQLite com SQLAlchemy ORM (pronto para PostgreSQL via `DATABASE_URL`)
- **Autenticação:** Bcrypt + JWT Session Cookies protegidos
- **Pagamentos:** SDK Oficial do Mercado Pago Developers (`mercadopago`)
- **Frontend:** HTML5 responsivo + Tailwind CSS + FontAwesome + Alpine.js
