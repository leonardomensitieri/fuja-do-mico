"""
MÓDULO: db_provider.py
======================
Provider de banco de dados Supabase para o pipeline Fuja do Mico.

O que faz:
  - Centraliza a conexão com o Supabase (PostgreSQL gerenciado)
  - Roteia dados de cada script para a tabela correta
  - Ativado SOMENTE quando SUPABASE_URL e SUPABASE_SERVICE_KEY estão configurados
  - Sem essas variáveis: todas as funções retornam None sem efeito (retrocompatibilidade)
  - Falha na persistência NUNCA aborta o pipeline — erros capturados no caller

Tabelas gerenciadas:
  - edicoes           : metadados de cada edição produzida
  - execucoes         : log de cada execução do pipeline (orchestration_report completo)
  - conteudo_coletado : itens coletados por fonte (ativado com SUPABASE_SALVAR_CONTEUDO=true)

Credenciais necessárias (GitHub Secrets):
  - SUPABASE_URL         : URL do projeto (https://{id}.supabase.co)
  - SUPABASE_SERVICE_KEY : Service Role Key — bypassa RLS, uso exclusivo server-side
"""

import os
from typing import Optional


def get_client():
    """
    Retorna cliente Supabase configurado ou None se credenciais ausentes.
    Importa supabase-py somente quando as env vars estão presentes.
    """
    url = os.environ.get('SUPABASE_URL')
    key = os.environ.get('SUPABASE_SERVICE_KEY')
    if not url or not key:
        return None
    from supabase import create_client
    return create_client(url, key)


def salvar_edicao(supabase, numero: int, titulo: str = None,
                  tipo_edicao: str = None, status: str = 'em_coleta',
                  id: str = None, github_run_id: str = None) -> Optional[str]:
    """
    Upsert na tabela edicoes.
    Retorna o UUID da edição criada/atualizada, ou None em caso de falha.

    Parâmetro id: quando fornecido, garante que o Supabase usa o mesmo UUID
    já propagado via os.environ['EDICAO_ID'], evitando violação de FK com execucoes.
    Parâmetro github_run_id: ID do run do GitHub Actions — usado para aprovação via
    Telegram e dashboard (Story 2.4).
    """
    upsert_data = {
        'numero': numero,
        'titulo': titulo,
        'tipo_edicao': tipo_edicao,
        'status': status,
    }
    if id:
        upsert_data['id'] = id
    if github_run_id:
        upsert_data['github_run_id'] = github_run_id
    resultado = supabase.table('edicoes').upsert(
        upsert_data, on_conflict='numero'
    ).execute()
    return resultado.data[0]['id'] if resultado.data else None


def salvar_execucao(supabase, edicao_id: str, orchestration_report: dict,
                    sucesso: bool, erro_mensagem: str = None) -> None:
    """Insert na tabela execucoes com o relatório completo de orquestração."""
    supabase.table('execucoes').insert({
        'edicao_id': edicao_id,
        'orchestration_report': orchestration_report,
        'sucesso': sucesso,
        'erro_mensagem': erro_mensagem,
    }).execute()


def salvar_conteudo_coletado(supabase, edicao_id: str,
                              fonte: str, itens: list) -> None:
    """
    Insert na tabela conteudo_coletado.
    Só executado quando SUPABASE_SALVAR_CONTEUDO=true (controle de volume).
    """
    supabase.table('conteudo_coletado').insert({
        'edicao_id': edicao_id,
        'fonte': fonte,
        'itens': itens,
    }).execute()


def _rotear_para_supabase(supabase, dados, arquivo: str,
                           edicao_id: str = None) -> None:
    """
    Roteia dados para a tabela correta conforme o arquivo de origem.
    Chamado pelo salvar_resultado() de cada script.

    Mapeamento:
      orchestration_report.json  → execucoes
      rss_raw.json / newsletters_raw.json /
      youtube_raw.json / social_raw.json → conteudo_coletado (se flag ativo)
    """
    if arquivo == 'orchestration_report.json':
        # Persiste execução com relatório completo
        tipo = dados.get('decisao', {}).get('tipo_edicao') if isinstance(dados, dict) else None
        sucesso = tipo != 'abortado'
        salvar_execucao(supabase, edicao_id, dados, sucesso)

    elif arquivo in ('rss_raw.json', 'newsletters_raw.json',
                     'youtube_raw.json', 'social_raw.json'):
        # Persiste conteúdo coletado somente se flag habilitado
        if os.environ.get('SUPABASE_SALVAR_CONTEUDO', '').lower() != 'true':
            return
        if isinstance(dados, list) and edicao_id:
            # Mapeia nome do arquivo para o campo 'fonte' da tabela
            fonte_map = {
                'newsletters_raw.json': 'gmail',
                'rss_raw.json': 'rss',
                'youtube_raw.json': 'youtube',
                'social_raw.json': 'social',
            }
            fonte = fonte_map.get(arquivo)
            if fonte:
                salvar_conteudo_coletado(supabase, edicao_id, fonte, dados)
