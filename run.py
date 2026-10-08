import uvicorn
from seed import seed_database

if __name__ == "__main__":
    seed_database()
    print("=" * 65)
    print("💈 BarberSaaS - Sistema de Gestão para Barbearias")
    print("🌐 Painel do Dono da Barbearia: http://localhost:8000/login")
    print("🔑 Acesso Demo: admin@barbearia.com  |  Senha: 123456")
    print("✂️ Página Pública do Cliente:   http://localhost:8000/b/dom-augusto")
    print("=" * 65)
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
