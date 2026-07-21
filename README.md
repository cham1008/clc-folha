# CLC Folha

Aplicativo Streamlit para tratamento e validação da folha contábil.

## Arquivos recebidos

- `CLC FOLHA.csv`
- `BALANCETE.xlsx`
- `CCs ATIVOS.xlsx`

## Arquivos gerados

- `BASE - CLC FOLHA.xlsx`
- `PRO-LABORE BASE.xlsx`
- `CLC FOLHA.csv`

## Publicação no Streamlit

1. Envie todos os arquivos deste projeto para a raiz do repositório GitHub.
2. No Streamlit Community Cloud use:
   - Repository: `cham1008/clc-folha`
   - Branch: `main`
   - Main file: `app.py`
3. Clique em **Deploy** ou reinicie o aplicativo em **Manage app**.

## Observação importante

A conversão automática de contas 3.3 para 3.4 depende da existência de uma correspondência segura no Balancete e da identificação do centro de custo como `DESPESA` na coluna de tipo/classificação do arquivo de centros de custo.
