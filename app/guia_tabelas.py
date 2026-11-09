"""Para que serve cada tabela: casos de uso e telas do Santé Admin que a usam.

Aparece no popup da lista de tabelas, na página Diagrama do banco (GET /api/banco/esquema).
A descrição curta vem da docstring do modelo; as relações vêm das chaves estrangeiras do banco.
"""

GUIA: dict[str, dict[str, list[str]]] = {
    # ---------- cadastro ----------
    "clinica": {
        "usos": [
            "Guardar nome, razão social, endereço e contatos da Santé.",
            "Definir as metas da casa: ocupação alvo, impostos e comissões sobre a receita.",
            "Definir o mínimo de turnos por reserva na agenda e a data da última atualização dos dados.",
        ],
        "telas": ["Visão geral", "Painel gerencial", "Comercial", "Base de dados"],
    },
    "espaco": {
        "usos": [
            "Cadastrar cada sala, piscina ou área como um centro de custo, com preço por hora e por turno.",
            "Servir de base para a agenda, os contratos e as despesas próprias de cada espaço.",
            "Calcular ocupação, receita e margem por espaço nos painéis.",
        ],
        "telas": ["Centros de custo", "Carteira de contratos", "Locatários", "Projeções e cenários", "Comercial"],
    },
    "turno": {
        "usos": [
            "Definir os horários que podem ser locados (manhã, tarde, noite...) e em que dias da semana.",
            "Turno sem espaço vale para a casa toda; turno com espaço substitui o da casa só naquela sala.",
            "Calcular a capacidade de cada espaço e a taxa de ocupação da agenda.",
        ],
        "telas": ["Centros de custo (detalhe do espaço)", "Painel gerencial"],
    },
    "despesa_espaco": {
        "usos": [
            "Lançar custos que pertencem a um espaço só (manutenção da piscina, equipamento da sala).",
            "Somar no resultado do centro de custo para ver a margem real de cada espaço.",
        ],
        "telas": ["Centros de custo"],
    },
    "custo_fixo": {
        "usos": [
            "Listar os custos mensais da casa: aluguel, energia, água, recepção, limpeza...",
            "Calcular o ponto de equilíbrio: quanto a Santé precisa faturar por mês para empatar.",
            "Ratear o custo da casa entre os espaços nas projeções.",
        ],
        "telas": ["Custos e equilíbrio", "Projeções e cenários", "Base de dados"],
    },
    "profissional": {
        "usos": [
            "Cadastrar os locatários: profissionais de saúde que alugam turnos ou salas.",
            "Ligar agendamentos e contratos a quem está usando o espaço.",
            "Acompanhar de onde veio cada locatário (canal) e seus dados de contato.",
        ],
        "telas": ["Locatários", "Centros de custo (agenda)", "Carteira de contratos"],
    },
    "profissional_link": {
        "usos": [
            "Guardar Instagram, LinkedIn, site e outras redes de cada locatário.",
            "Mostrar os links no cadastro do profissional.",
        ],
        "telas": ["Locatários"],
    },
    # ---------- operação ----------
    "agendamento": {
        "usos": [
            "Marcar na agenda de um espaço quais turnos de um dia foram locados e para quem.",
            "Bloquear turnos como \"Não disponível\" (manutenção, uso da casa).",
            "Medir a ocupação real e a receita avulsa do mês.",
        ],
        "telas": ["Centros de custo (agenda)", "Locatários", "Carteira de contratos"],
    },
    "contrato": {
        "usos": [
            "Registrar locações recorrentes: quantas horas, turnos ou meses por mês e a que preço.",
            "Formar a carteira de contratos e a receita recorrente prevista para cada mês.",
            "Saber qual campanha trouxe o cliente, para medir o retorno do marketing.",
        ],
        "telas": ["Carteira de contratos", "Centros de custo", "Projeções e cenários", "Comercial"],
    },
    "campanha": {
        "usos": [
            "Registrar ações comerciais (anúncio, parceria, evento) com orçamento e período.",
            "Acompanhar leads e visitas e comparar com os contratos que a campanha gerou.",
            "Calcular custo por lead e retorno de cada campanha.",
        ],
        "telas": ["Comercial", "Carteira de contratos", "Centros de custo"],
    },
    "campanha_espaco": {
        "usos": [
            "Dizer quais espaços cada campanha divulga (uma campanha pode cobrir vários espaços).",
            "Filtrar as campanhas que afetam um espaço.",
        ],
        "telas": ["Comercial", "Centros de custo"],
    },
    # ---------- mercado ----------
    "coleta": {
        "usos": [
            "Registrar quando os dados de mercado ou do monitor social foram coletados.",
            "Mostrar a data da coleta nas páginas, para saber se os números estão velhos.",
        ],
        "telas": ["Análise de mercado", "Monitor social"],
    },
    "concorrente": {
        "usos": [
            "Comparar a Santé com os outros espaços de saúde de Maceió: preço, modalidades, horário, diferenciais.",
            "Classificar o nível de ameaça de cada concorrente.",
            "Ser a base para preços, sites e perfis sociais de cada player.",
        ],
        "telas": ["Análise de mercado", "Monitor social"],
    },
    "preco_hora": {
        "usos": [
            "Guardar cada preço por hora anunciado por um concorrente (por faixa ou serviço).",
            "Comparar a faixa de preço da Santé com a do mercado.",
        ],
        "telas": ["Análise de mercado"],
    },
    "busca_mapa": {
        "usos": [
            "Registrar em que posição a Santé aparece no Google Maps para cada busca.",
            "Ver quem aparece no topo das buscas importantes.",
        ],
        "telas": ["Análise de mercado"],
    },
    "avaliacao_site": {
        "usos": [
            "Guardar as notas do PageSpeed (desempenho, acessibilidade, SEO) do site de cada concorrente.",
            "Comparar a qualidade do site da Santé com a dos concorrentes.",
        ],
        "telas": ["Análise de mercado"],
    },
    "trafego_site": {
        "usos": [
            "Registrar o que o Similarweb mostrou sobre o tráfego de cada site.",
        ],
        "telas": ["Análise de mercado"],
    },
    "rede_social": {
        "usos": [
            "Listar as redes acompanhadas (Instagram, Facebook, YouTube...) e por que cada uma importa.",
            "Agrupar os perfis sociais por rede.",
        ],
        "telas": ["Monitor social"],
    },
    "perfil_social": {
        "usos": [
            "Guardar o perfil de cada concorrente em cada rede: seguidores, publicações, situação.",
            "Ver quem está ativo, parado ou sem perfil comercial.",
        ],
        "telas": ["Monitor social", "Análise de mercado"],
    },
    "post_social": {
        "usos": [
            "Guardar as publicações recentes de cada perfil com data, tipo, curtidas e legenda.",
            "Buscar por palavra, @perfil ou #hashtag e medir engajamento no monitor social.",
        ],
        "telas": ["Monitor social"],
    },
    "busca_youtube": {
        "usos": [
            "Registrar buscas no YouTube por termos do setor e os vídeos que se destacam.",
            "Avaliar se vale a pena a Santé produzir vídeo.",
        ],
        "telas": ["Monitor social"],
    },
    # ---------- sistema ----------
    "diagrama_posicao": {
        "usos": [
            "Guardar onde cada tabela foi colocada à mão neste diagrama.",
            "\"Arrumação automática\" apaga estas linhas e volta ao desenho calculado.",
        ],
        "telas": ["Diagrama do banco"],
    },
    "aerich": {
        "usos": [
            "Controlar quais migrações do banco já foram aplicadas (ferramenta Aerich).",
            "Não é dado do negócio: não editar à mão.",
        ],
        "telas": [],
    },
}
