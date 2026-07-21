from __future__ import annotations

from io import BytesIO, StringIO
import csv
import re
import unicodedata
from typing import Dict, List, Tuple

import pandas as pd


def sem_acento(texto: object) -> str:
    valor = "" if texto is None else str(texto)
    valor = unicodedata.normalize("NFKD", valor)
    return "".join(c for c in valor if not unicodedata.combining(c))


def normalizar_nome(texto: object) -> str:
    valor = sem_acento(texto).upper().strip()
    valor = re.sub(r"[^A-Z0-9]+", " ", valor)
    return re.sub(r"\s+", " ", valor).strip()


def texto_codigo(valor: object) -> str:
    if valor is None or pd.isna(valor):
        return ""
    texto = str(valor).strip()
    if texto.endswith(".0"):
        texto = texto[:-2]
    return texto


def ler_csv_folha(conteudo: bytes) -> pd.DataFrame:
    ultimo_erro = None

    for encoding in ("latin1", "cp1252", "utf-8-sig", "utf-8"):
        try:
            texto = conteudo.decode(encoding)
        except UnicodeDecodeError as erro:
            ultimo_erro = erro
            continue

        primeira = texto.splitlines()[0] if texto.splitlines() else ""
        separador = ";" if primeira.count(";") >= primeira.count(",") else ","

        leitor = csv.reader(StringIO(texto), delimiter=separador)
        linhas = list(leitor)
        if not linhas:
            raise ValueError("O arquivo CSV está vazio.")

        cabecalho = [str(c).strip() for c in linhas[0]]
        dados = []
        for linha in linhas[1:]:
            if not any(str(v).strip() for v in linha):
                continue
            if len(linha) > len(cabecalho):
                extras = linha[len(cabecalho):]
                linha = linha[:len(cabecalho)]
                if extras and not any(str(v).strip() for v in extras):
                    pass
            if len(linha) < len(cabecalho):
                linha += [""] * (len(cabecalho) - len(linha))
            dados.append(linha[:len(cabecalho)])

        return pd.DataFrame(dados, columns=cabecalho, dtype=str)

    raise ValueError(f"Não foi possível identificar a codificação do CSV: {ultimo_erro}")


def encontrar_coluna(df: pd.DataFrame, possibilidades: List[str], obrigatoria: bool = True) -> str | None:
    mapa = {normalizar_nome(col): col for col in df.columns}
    for nome in possibilidades:
        chave = normalizar_nome(nome)
        if chave in mapa:
            return mapa[chave]

    for chave, original in mapa.items():
        for nome in possibilidades:
            alvo = normalizar_nome(nome)
            if alvo in chave or chave in alvo:
                return original

    if obrigatoria:
        raise ValueError(
            "Coluna obrigatória não encontrada. Esperado um dos nomes: "
            + ", ".join(possibilidades)
        )
    return None


def valor_para_centavos(valor: object) -> int:
    texto = "" if valor is None else str(valor).strip()
    if not texto:
        return 0

    texto = texto.replace("R$", "").replace(" ", "")
    negativo = texto.startswith("-")
    texto = texto.lstrip("+-")

    # Se houver vírgula, assume padrão brasileiro.
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
        numero = float(texto)
        return abs(int(round(numero * 100)))

    # Se houver ponto com 1 ou 2 casas finais, assume decimal.
    if re.fullmatch(r"\d+\.\d{1,2}", texto):
        return abs(int(round(float(texto) * 100)))

    # Inteiro é considerado já em centavos.
    somente_digitos = re.sub(r"\D", "", texto)
    return abs(int(somente_digitos or 0))


def formatar_data(valor: object) -> str:
    texto = "" if valor is None else str(valor).strip()
    if not texto:
        return ""

    somente = re.sub(r"\D", "", texto)
    if len(somente) == 8:
        # aceita DDMMAAAA ou AAAAMMDD
        if int(somente[:4]) >= 1900:
            return somente[6:8] + somente[4:6] + somente[:4]
        return somente

    data = pd.to_datetime(texto, dayfirst=True, errors="coerce")
    if pd.isna(data):
        return ""
    return data.strftime("%d%m%Y")


def preparar_balancete(conteudo: bytes) -> pd.DataFrame:
    df = pd.read_excel(BytesIO(conteudo), dtype=str)
    conta = encontrar_coluna(df, ["CONTA", "CODIGO DA CONTA", "COD CONTA"])
    classificacao = encontrar_coluna(df, ["CLASSIFICACAO", "CLASSIFICAÇÃO"])
    descricao = encontrar_coluna(df, ["DESCRICAO", "DESCRIÇÃO"])

    saida = pd.DataFrame({
        "CONTA": df[conta].map(texto_codigo),
        "CLASSIFICACAO": df[classificacao].fillna("").astype(str).str.strip(),
        "DESCRICAO": df[descricao].fillna("").astype(str).str.strip(),
    })
    return saida[saida["CONTA"] != ""].drop_duplicates("CONTA")


def preparar_centros(conteudo: bytes) -> pd.DataFrame:
    bruto = pd.read_excel(BytesIO(conteudo), header=None, dtype=str)

    linha_cabecalho = None
    for indice, linha in bruto.iterrows():
        normalizados = [normalizar_nome(v) for v in linha.tolist()]
        if "CODIGO" in normalizados and "DESCRICAO" in normalizados:
            linha_cabecalho = indice
            break

    if linha_cabecalho is None:
        raise ValueError("Não foi localizado o cabeçalho no arquivo de centros de custo.")

    cabecalho = []
    for i, valor in enumerate(bruto.iloc[linha_cabecalho].tolist()):
        nome = str(valor).strip() if not pd.isna(valor) else ""
        cabecalho.append(nome or f"COLUNA_{i}")

    dados = bruto.iloc[linha_cabecalho + 1:].copy()
    dados.columns = cabecalho

    codigo = encontrar_coluna(dados, ["CODIGO", "CÓDIGO"])
    descricao = encontrar_coluna(dados, ["DESCRICAO", "DESCRIÇÃO"])
    unidade = encontrar_coluna(dados, ["UNIDADE"])
    estabelecimento = encontrar_coluna(
        dados,
        ["CODIGO DO ESTABELECIMENTO", "CÓDIGO DO ESTABELECIMENTO", "ESTABELECIMENTO"]
    )
    tipo = encontrar_coluna(dados, ["TIPO", "CLASSIFICACAO", "CUSTO DESPESA"], obrigatoria=False)

    saida = pd.DataFrame({
        "CENTRO_CUSTO": dados[codigo].map(texto_codigo),
        "DESCRICAO_CC": dados[descricao].fillna("").astype(str).str.strip(),
        "UNIDADE_CC": dados[unidade].fillna("").astype(str).str.strip(),
        "FILIAL_CC": dados[estabelecimento].map(texto_codigo),
        "TIPO_CC": dados[tipo].fillna("").astype(str).str.strip() if tipo else "",
    })
    return saida[saida["CENTRO_CUSTO"] != ""].drop_duplicates("CENTRO_CUSTO")


def criar_mapas_contas(balancete: pd.DataFrame) -> Tuple[Dict[str, str], Dict[str, str]]:
    por_descricao = {}
    for _, linha in balancete.iterrows():
        chave = normalizar_nome(linha["DESCRICAO"])
        if chave:
            por_descricao[chave] = linha["CONTA"]

    mapa_33_34 = {}
    por_desc_sem_grupo = {}

    for _, linha in balancete.iterrows():
        desc = normalizar_nome(linha["DESCRICAO"])
        classe = str(linha["CLASSIFICACAO"]).strip()
        chave_desc = re.sub(r"\b(CUSTO|DESPESA|CUSTOS|DESPESAS)\b", "", desc)
        chave_desc = re.sub(r"\s+", " ", chave_desc).strip()
        por_desc_sem_grupo.setdefault(chave_desc, []).append(linha)

    for itens in por_desc_sem_grupo.values():
        contas_33 = [i for i in itens if str(i["CLASSIFICACAO"]).startswith("3.3")]
        contas_34 = [i for i in itens if str(i["CLASSIFICACAO"]).startswith("3.4")]
        if len(contas_33) == 1 and len(contas_34) == 1:
            mapa_33_34[str(contas_33[0]["CONTA"])] = str(contas_34[0]["CONTA"])

    mapa_b2b_b2c = {}
    for _, linha in balancete.iterrows():
        desc = normalizar_nome(linha["DESCRICAO"])
        if "B2B" not in desc:
            continue
        alvo_desc = desc.replace("B2B", "B2C")
        candidatos = balancete[
            balancete["DESCRICAO"].map(normalizar_nome) == alvo_desc
        ]
        if len(candidatos) == 1:
            mapa_b2b_b2c[str(linha["CONTA"])] = str(candidatos.iloc[0]["CONTA"])

    return mapa_33_34, mapa_b2b_b2c


def montar_excel_base(
    base_original: pd.DataFrame,
    base_corrigida: pd.DataFrame,
    alteracoes: pd.DataFrame,
    pendencias: pd.DataFrame,
) -> bytes:
    memoria = BytesIO()

    with pd.ExcelWriter(memoria, engine="xlsxwriter") as writer:
        base_corrigida.to_excel(writer, sheet_name="Base Corrigida", index=False)
        base_original.to_excel(writer, sheet_name="Base Original", index=False)

        resumo_unidade = (
            base_corrigida.groupby(["UNIDADE"], dropna=False)["VALOR"]
            .agg(QUANTIDADE="count", VALOR_TOTAL="sum")
            .reset_index()
        )
        resumo_unidade.to_excel(writer, sheet_name="Resumo por Unidade", index=False)

        resumo_filial = (
            base_corrigida.groupby(["COD FILIAL"], dropna=False)["VALOR"]
            .agg(QUANTIDADE="count", VALOR_TOTAL="sum")
            .reset_index()
        )
        resumo_filial.to_excel(writer, sheet_name="Resumo por Filial", index=False)

        resumo_cc = (
            base_corrigida.groupby(
                ["COD CENTRO DE CUSTO", "DESCRICAO CENTRO DE CUSTO", "UNIDADE", "COD FILIAL"],
                dropna=False
            )["VALOR"]
            .agg(QUANTIDADE="count", VALOR_TOTAL="sum")
            .reset_index()
        )
        resumo_cc.to_excel(writer, sheet_name="Resumo por CC", index=False)

        alteracoes.to_excel(writer, sheet_name="Contas Alteradas", index=False)
        pendencias.to_excel(writer, sheet_name="Pendências", index=False)

        validacao = pd.DataFrame([
            ["Total base original", len(base_original)],
            ["Total base principal", len(base_corrigida)],
            ["Total de alterações", len(alteracoes)],
            ["Total de pendências", len(pendencias)],
            ["Valor original", int(base_original["VALOR"].sum())],
            ["Valor base principal", int(base_corrigida["VALOR"].sum())],
        ], columns=["VALIDAÇÃO", "RESULTADO"])
        validacao.to_excel(writer, sheet_name="Validação Contábil", index=False)

        formatar_planilhas(writer)

    return memoria.getvalue()


def montar_excel_prolabore(
    prolabore: pd.DataFrame,
    alteracoes: pd.DataFrame,
    pendencias: pd.DataFrame,
) -> bytes:
    memoria = BytesIO()

    with pd.ExcelWriter(memoria, engine="xlsxwriter") as writer:
        prolabore.to_excel(writer, sheet_name="Base Pró-labore", index=False)

        resumo = pd.DataFrame([
            ["Quantidade de lançamentos", len(prolabore)],
            ["Valor total", int(prolabore["VALOR"].sum()) if not prolabore.empty else 0],
            ["Filial aplicada", "741"],
            ["Centro de custo", "1010"],
        ], columns=["INDICADOR", "RESULTADO"])
        resumo.to_excel(writer, sheet_name="Resumo", index=False)

        alteracoes.to_excel(writer, sheet_name="Contas Alteradas", index=False)
        pendencias.to_excel(writer, sheet_name="Pendências", index=False)

        formatar_planilhas(writer)

    return memoria.getvalue()


def formatar_planilhas(writer: pd.ExcelWriter) -> None:
    workbook = writer.book
    formato_header = workbook.add_format({
        "bold": True,
        "font_color": "white",
        "bg_color": "#102A43",
        "border": 1,
        "align": "center",
        "valign": "vcenter",
    })
    formato_valor = workbook.add_format({"num_format": "#,##0"})
    formato_texto = workbook.add_format({"num_format": "@"})

    for nome, worksheet in writer.sheets.items():
        worksheet.freeze_panes(1, 0)
        worksheet.autofilter(0, 0, max(0, worksheet.dim_rowmax), max(0, worksheet.dim_colmax))
        worksheet.set_row(0, 24, formato_header)
        worksheet.set_column(0, max(0, worksheet.dim_colmax), 18)
        worksheet.set_column(0, 0, 14, formato_texto)

        if "Base" in nome:
            worksheet.set_column(0, max(0, worksheet.dim_colmax), 18)
            worksheet.set_column(max(0, worksheet.dim_colmax), max(0, worksheet.dim_colmax), 45)


def processar_arquivos(csv_bytes: bytes, balancete_bytes: bytes, cc_bytes: bytes) -> dict:
    bruto = ler_csv_folha(csv_bytes)
    balancete = preparar_balancete(balancete_bytes)
    centros = preparar_centros(cc_bytes)

    col_data = encontrar_coluna(bruto, ["DATA"])
    col_filial = encontrar_coluna(bruto, ["UNIDADE", "FILIAL", "COD FILIAL"])
    col_debito = encontrar_coluna(bruto, ["C DEBITO", "CONTA DEBITO", "DEBITO"])
    col_credito = encontrar_coluna(bruto, ["C CREDITO", "CONTA CREDITO", "CREDITO"])
    col_valor = encontrar_coluna(bruto, ["VALOR"])
    col_cc = encontrar_coluna(bruto, ["CENTRO DE CUSTO", "COD CENTRO DE CUSTO"])
    col_hist = encontrar_coluna(bruto, ["CODIGO DO HISTORICO", "COD HIST"])
    col_comp = encontrar_coluna(bruto, ["HISTORICO COMPLEMENTAR", "COMPLEMENTO"], obrigatoria=False)

    base = pd.DataFrame({
        "DATA": bruto[col_data].map(formatar_data),
        "COD FILIAL ORIGINAL": bruto[col_filial].map(texto_codigo),
        "DEBITO ORIGINAL": bruto[col_debito].map(texto_codigo),
        "CREDITO ORIGINAL": bruto[col_credito].map(texto_codigo),
        "VALOR": bruto[col_valor].map(valor_para_centavos),
        "COD CENTRO DE CUSTO": bruto[col_cc].map(texto_codigo),
        "COD HIST": "116",
        "COMPLEMENTO": bruto[col_comp].fillna("").astype(str).str.strip() if col_comp else "",
    })

    base["COD FILIAL"] = base["COD FILIAL ORIGINAL"]
    base["DEBITO"] = base["DEBITO ORIGINAL"]
    base["CREDITO"] = base["CREDITO ORIGINAL"]
    base["STATUS"] = "OK"
    base["MOTIVO DA ALTERACAO"] = ""

    base = base.merge(
        centros,
        how="left",
        left_on="COD CENTRO DE CUSTO",
        right_on="CENTRO_CUSTO"
    )

    base["DESCRICAO CENTRO DE CUSTO"] = base["DESCRICAO_CC"].fillna("")
    base["UNIDADE"] = base["UNIDADE_CC"].fillna("")

    alteracoes = []
    pendencias = []

    contas_validas = set(balancete["CONTA"])
    desc_por_conta = dict(zip(balancete["CONTA"], balancete["DESCRICAO"]))
    classe_por_conta = dict(zip(balancete["CONTA"], balancete["CLASSIFICACAO"]))

    mapa_33_34, mapa_b2b_b2c = criar_mapas_contas(balancete)

    conta_fgts = next(
        (c for c, d in desc_por_conta.items() if normalizar_nome(d) == "FGTS A RECOLHER"),
        "98620"
    )
    conta_salarios = next(
        (c for c, d in desc_por_conta.items() if normalizar_nome(d) == "SALARIOS A PAGAR"),
        "98609"
    )

    for indice, linha in base.iterrows():
        motivos = []

        # Filial conforme centro de custo
        filial_cc = texto_codigo(linha.get("FILIAL_CC", ""))
        if filial_cc and filial_cc != linha["COD FILIAL"]:
            anterior = linha["COD FILIAL"]
            base.at[indice, "COD FILIAL"] = filial_cc
            motivos.append(f"Filial {anterior} alterada para {filial_cc} conforme CC")
            alteracoes.append({
                "LINHA": indice + 2,
                "CAMPO": "FILIAL",
                "VALOR ORIGINAL": anterior,
                "VALOR CORRIGIDO": filial_cc,
                "MOTIVO": "Filial do centro de custo",
            })

        # FGTS no crédito -> Salários a pagar
        if linha["CREDITO"] == conta_fgts:
            base.at[indice, "CREDITO"] = conta_salarios
            motivos.append("FGTS a recolher alterado para Salários a pagar no crédito")
            alteracoes.append({
                "LINHA": indice + 2,
                "CAMPO": "CREDITO",
                "VALOR ORIGINAL": conta_fgts,
                "VALOR CORRIGIDO": conta_salarios,
                "MOTIVO": "Regra FGTS",
            })

        # B2B -> B2C somente no crédito
        credito_atual = base.at[indice, "CREDITO"]
        if credito_atual in mapa_b2b_b2c:
            novo = mapa_b2b_b2c[credito_atual]
            base.at[indice, "CREDITO"] = novo
            motivos.append(f"Conta B2B {credito_atual} alterada para B2C {novo}")
            alteracoes.append({
                "LINHA": indice + 2,
                "CAMPO": "CREDITO",
                "VALOR ORIGINAL": credito_atual,
                "VALOR CORRIGIDO": novo,
                "MOTIVO": "Regra B2B para B2C",
            })

        # 3.3 -> 3.4 para centros marcados como despesa
        tipo_cc = normalizar_nome(linha.get("TIPO_CC", ""))
        centro_despesa = "DESPESA" in tipo_cc

        if centro_despesa:
            for campo in ("DEBITO", "CREDITO"):
                conta_atual = base.at[indice, campo]
                if conta_atual in mapa_33_34:
                    nova = mapa_33_34[conta_atual]
                    base.at[indice, campo] = nova
                    motivos.append(f"{campo} {conta_atual} convertido de 3.3 para 3.4 ({nova})")
                    alteracoes.append({
                        "LINHA": indice + 2,
                        "CAMPO": campo,
                        "VALOR ORIGINAL": conta_atual,
                        "VALOR CORRIGIDO": nova,
                        "MOTIVO": "Centro de custo de despesa",
                    })

        if not linha["DATA"]:
            pendencias.append({
                "LINHA": indice + 2,
                "TIPO": "DATA INVÁLIDA",
                "DETALHE": "Data não reconhecida",
            })

        if not linha["COD CENTRO DE CUSTO"] or not filial_cc:
            pendencias.append({
                "LINHA": indice + 2,
                "TIPO": "CENTRO DE CUSTO",
                "DETALHE": f"Centro de custo {linha['COD CENTRO DE CUSTO']} não encontrado",
            })

        for campo in ("DEBITO", "CREDITO"):
            conta = base.at[indice, campo]
            if conta not in contas_validas:
                pendencias.append({
                    "LINHA": indice + 2,
                    "TIPO": f"CONTA {campo}",
                    "DETALHE": f"Conta {conta} não encontrada no balancete",
                })

        if int(linha["VALOR"]) == 0:
            pendencias.append({
                "LINHA": indice + 2,
                "TIPO": "VALOR",
                "DETALHE": "Valor zerado",
            })

        if base.at[indice, "DEBITO"] == base.at[indice, "CREDITO"]:
            pendencias.append({
                "LINHA": indice + 2,
                "TIPO": "DÉBITO = CRÉDITO",
                "DETALHE": f"Conta {base.at[indice, 'DEBITO']}",
            })

        if motivos:
            base.at[indice, "STATUS"] = "AJUSTADO"
            base.at[indice, "MOTIVO DA ALTERACAO"] = " | ".join(motivos)

    # Pró-labore
    mascara_prolabore = base["COD CENTRO DE CUSTO"] == "1010"
    prolabore = base[mascara_prolabore].copy()
    prolabore["COD FILIAL"] = "741"
    if not prolabore.empty:
        prolabore["MOTIVO DA ALTERACAO"] = (
            prolabore["MOTIVO DA ALTERACAO"].astype(str)
            .str.strip(" |")
            .replace("", "Pró-labore: filial definida como 741")
        )

    base_principal = base[~mascara_prolabore].copy()

    colunas_saida = [
        "DATA",
        "COD FILIAL",
        "DEBITO",
        "CREDITO",
        "VALOR",
        "COD CENTRO DE CUSTO",
        "COD HIST",
        "COMPLEMENTO",
        "DESCRICAO CENTRO DE CUSTO",
        "UNIDADE",
        "STATUS",
        "MOTIVO DA ALTERACAO",
        "COD FILIAL ORIGINAL",
        "DEBITO ORIGINAL",
        "CREDITO ORIGINAL",
    ]

    base_principal = base_principal[colunas_saida]
    prolabore = prolabore[colunas_saida]

    alteracoes_df = pd.DataFrame(
        alteracoes,
        columns=["LINHA", "CAMPO", "VALOR ORIGINAL", "VALOR CORRIGIDO", "MOTIVO"]
    )
    pendencias_df = pd.DataFrame(
        pendencias,
        columns=["LINHA", "TIPO", "DETALHE"]
    )

    base_original = base[[
        "DATA",
        "COD FILIAL ORIGINAL",
        "DEBITO ORIGINAL",
        "CREDITO ORIGINAL",
        "VALOR",
        "COD CENTRO DE CUSTO",
        "COD HIST",
        "COMPLEMENTO",
    ]].copy()

    base_excel = montar_excel_base(
        base_original,
        base_principal,
        alteracoes_df,
        pendencias_df
    )
    prolabore_excel = montar_excel_prolabore(
        prolabore,
        alteracoes_df,
        pendencias_df
    )

    csv_colunas = [
        "DATA",
        "COD FILIAL",
        "DEBITO",
        "CREDITO",
        "VALOR",
        "COD CENTRO DE CUSTO",
        "COD HIST",
        "COMPLEMENTO",
    ]

    # CSV final inclui base principal + pró-labore.
    final_csv_df = pd.concat(
        [base_principal[csv_colunas], prolabore[csv_colunas]],
        ignore_index=True
    )
    csv_final = final_csv_df.to_csv(
        index=False,
        sep=",",
        encoding="utf-8-sig",
        lineterminator="\n"
    ).encode("utf-8-sig")

    return {
        "base_excel": base_excel,
        "prolabore_excel": prolabore_excel,
        "csv_final": csv_final,
        "preview": base_principal.head(100),
        "metricas": {
            "total_lancamentos": len(base),
            "base_principal": len(base_principal),
            "pro_labore": len(prolabore),
            "ajustes": len(alteracoes_df),
            "pendencias": len(pendencias_df),
            "valor_total_centavos": int(base["VALOR"].sum()),
        },
    }
