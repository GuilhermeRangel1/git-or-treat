"""Reconcilia amostras das páginas WEB com SQL independente, sem publicar valores/UCs."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import http.cookiejar
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--credentials', type=Path, required=True)
    parser.add_argument('--api-base', default='http://127.0.0.1:8015')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if urllib.parse.urlsplit(args.api_base).hostname not in {'localhost','127.0.0.1'}:
        parser.error('Use somente API local autorizada.')
    private = args.credentials.read_text(encoding='utf-8')
    output = args.output.resolve()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(root/'backend'))
    os.chdir(root/'backend')
    from app.core.config import settings
    from sqlalchemy import create_engine, text
    engine = create_engine(settings.DATABASE_URL, hide_parameters=True)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    checks = []

    def call(path, data=None):
        request=urllib.request.Request(args.api_base+'/api/v1'+path,
            data=json.dumps(data).encode() if data is not None else None,
            headers={'Origin':'http://127.0.0.1:5173','Content-Type':'application/json'})
        try:
            response=opener.open(request,timeout=30)
        except urllib.error.HTTPError as error:
            response=error
        raw=response.read()
        return response.code,json.loads(raw) if raw else {}

    def check(name, passed):
        checks.append({'check':name,'passed':bool(passed)})

    def close(actual, expected, tolerance='.01'):
        if actual is None or expected is None:
            return actual is None and expected is None
        return abs(Decimal(str(actual))-Decimal(str(expected))) <= Decimal(tolerance)

    def get(path):
        code, body=call(path)
        if code != 200:
            check('http:'+path.split('?')[0],False)
            raise RuntimeError('Unexpected HTTP status')
        return body

    publication = None
    try:
        code,_=call('/auth/login',{'username':re.findall(r'^admin username: (.+)',private,re.M)[-1].strip(),'password':re.findall(r'^admin password: (.+)',private,re.M)[-1].strip()})
        check('login',code==200)
        with engine.connect().execution_options(isolation_level='REPEATABLE READ') as db:
            db.execute(text('SET TRANSACTION READ ONLY'))
            publication=dict(db.execute(text('SELECT lote,fingerprint,schema_version FROM gold_carga_atual WHERE id=1')).mappings().one())
            panorama=get('/panorama?comparacao=nenhuma')
            check('same_publication',panorama['metadata']['fingerprint']==publication['fingerprint'] and panorama['metadata']['source']['version']==publication['lote'])
            if not checks[-1]['passed']:
                raise RuntimeError('Publication differs')
            month=panorama['data']['filtros']['periodo']
            sample=dict(db.execute(text('SELECT municipio,bairro,classe_consumo FROM gold_v2.consumo_receita_bairro WHERE competencia=:m ORDER BY municipio,bairro,classe_consumo LIMIT 1'),{'m':month}).mappings().one())
            sample['classe']=sample.pop('classe_consumo')
            contexts=[{}, {'municipio':sample['municipio']}, {'municipio':sample['municipio'],'classe':sample['classe']}, sample]
            components={'volume':'efeito_volume_reais','preco':'efeito_preco_observado_reais','interacao':'efeito_interacao_reais','entradas':'variacao_entradas_reais','saidas':'variacao_saidas_reais','sem_leitura':'variacao_sem_leitura_fora_base_reais','outros':'variacao_outros_fora_base_reais'}
            for index,filters in enumerate(contexts):
                params={'competencia_inicio':month,'competencia_fim':month,**filters}
                revenue=get('/revenue?'+urllib.parse.urlencode(params))['data']
                conditions=' AND '.join(f"{('classe_consumo' if key=='classe' else key)}=:{key}" for key in filters)
                conditions=(' AND '+conditions) if conditions else ''
                values={'m':month,**filters}
                row=db.execute(text('SELECT sum(receita_total_reais) AS revenue,sum(consumo_total_kwh) AS energy FROM gold_v2.consumo_receita_bairro WHERE competencia=:m'+conditions),values).mappings().one()
                check(f'revenue_{index}:observed_money',close(revenue['total_billed_amount'],row['revenue']))
                check(f'revenue_{index}:measured_energy',close(revenue['total_measured_energy_kwh'],row['energy']))
                check(f'revenue_{index}:absent_paid_and_billed_energy',revenue['total_paid_amount'] is None and revenue['total_billed_energy_kwh'] is None)
                decomposition=revenue['window_decomposition']
                for label,column in components.items():
                    expected=db.scalar(text(f'SELECT sum({column}) FROM gold_v2.decomposicao_receita WHERE true'+conditions),filters)
                    check(f'revenue_{index}:decomposition_{label}',close(decomposition['components'].get(label),expected))
                for dimension in ['municipio','bairro','classe']:
                    breakdown=get('/revenue?'+urllib.parse.urlencode({**params,'group_by':dimension}))['data']['breakdown']
                    total=sum(Decimal(str(item['comparison']['final']['billed_amount'])) for item in breakdown['items'] if item['comparison']['final']['billed_amount'] is not None)
                    check(f'revenue_{index}:breakdown_{dimension}',close(total,row['revenue']))
            # Cada histórico usa sua própria fonte e seu relógio, sem inferir cobertura.
            uc=db.scalar(text('SELECT id_uc FROM gold_v2.faturas_uc GROUP BY id_uc ORDER BY count(*) DESC,id_uc LIMIT 1'))
            first,last=db.execute(text('SELECT min(competencia),max(competencia) FROM gold_v2.consumo_mensal_uc')).one()
            start=datetime(int(first[:4]),int(first[5:]),1,tzinfo=timezone.utc)
            end=datetime(int(last[:4])+(last[5:]=='12'),int(last[5:])%12+1,1,tzinfo=timezone.utc)
            scope={'uc':uc,'first':first,'last':last,'start':start,'end':end}
            uc_path='/ucs/'+urllib.parse.quote(uc,safe='')
            period=urllib.parse.urlencode({'start':first,'end':last,'page_size':100})
            source_queries={
                'consumption': 'SELECT count(*) FROM gold_v2.consumo_mensal_uc WHERE id_uc=:uc AND competencia BETWEEN :first AND :last',
                'invoices':'SELECT count(*) FROM gold_v2.faturas_uc WHERE id_uc=:uc AND mes_referencia BETWEEN :first AND :last',
                'meters':'SELECT count(*) FROM gold_v2.medidor_uc WHERE id_uc=:uc',
                'calls':'SELECT count(*) FROM gold_v2.atendimentos_uc WHERE id_uc=:uc AND data_abertura>=:start AND data_abertura<:end',
                'interruptions':'SELECT count(*) FROM gold_v2.ocorrencias_uc WHERE id_uc=:uc AND data_abertura>=:start AND data_abertura<:end',
                'treatments':'SELECT count(*) FROM gold_v2.tratativas_uc t JOIN gold_v2.atendimentos_uc a ON t.protocolo=a.protocolo AND t.id_uc=a.id_uc WHERE t.id_uc=:uc AND a.data_abertura>=:start AND a.data_abertura<:end',
            }
            for section,query in source_queries.items():
                history=get(uc_path+'/history/'+section+'?'+period)
                check('uc:'+section+'_count',history['pagination']['total']==db.scalar(text(query),scope))
                if section=='invoices':
                    for index,item in enumerate(history['data']['items']):
                        expected=db.execute(text('SELECT valor_total,status,valor_fatura_declarada_em_aberto_reais FROM gold_v2.faturas_uc WHERE id_uc=:uc AND id_fatura=:invoice'),{'uc':uc,'invoice':item['invoice_id']}).mappings().one()
                        check(f'uc:invoice_{index}_values',close(item['billed_amount'],expected['valor_total']) and item['declared_status']==expected['status'] and close(item['declared_open_amount'],expected['valor_fatura_declarada_em_aberto_reais']) and item['paid_amount'] is None)
            overview=get(uc_path+'/overview?'+urllib.parse.urlencode({'start':first,'end':last}))['data']
            gd=db.execute(text('SELECT potencia_kwp FROM gold_v2.gd_uc WHERE id_uc=:uc'),{'uc':uc}).first()
            check('uc:gd_capacity',close(overview['gold_generation']['capacity_kwp'] if overview['gold_generation'] else None,gd[0] if gd else None))
            check('uc:profile_matches_identifier',overview['profile']['uc_id']==uc)
            # Paginação e ordenação da fila contra a ordenação física declarada.
            queue=get('/inspections/queue?page_size=20')
            expected=db.execute(text('SELECT id_uc,posicao_fila_inspecao,prioridade_inspecao,motivo_prioridade,energia_estimada_recuperavel_kwh FROM gold_v2.fila_inspecao ORDER BY posicao_fila_inspecao ASC NULLS LAST,id_uc ASC LIMIT 20')).mappings().all()
            check('queue:count',queue['pagination']['total']==db.scalar(text('SELECT count(*) FROM gold_v2.fila_inspecao')))
            check('queue:ordered_page', [item['uc_id'] for item in queue['data']['items']]==[row['id_uc'] for row in expected])
            for index,(item,row) in enumerate(zip(queue['data']['items'],expected)):
                check(f'queue:item_{index}',item['category']==row['prioridade_inspecao'] and item['reason']==row['motivo_prioridade'] and item['queue_position']==row['posicao_fila_inspecao'] and close(item['potential_recoverable_energy_kwh'],row['energia_estimada_recuperavel_kwh']))
            second=get('/inspections/queue?page_size=20&page=2')
            check('queue:second_page_disjoint',not ({item['uc_id'] for item in queue['data']['items']} & {item['uc_id'] for item in second['data']['items']}))
            for direction in ('asc','desc'):
                sorted_queue=get('/inspections/queue?'+urllib.parse.urlencode({
                    'page_size':50,
                    'order_by':'potential_recoverable_energy_kwh',
                    'direction':direction,
                }))
                items=sorted_queue['data']['items']
                estimates=[item['potential_recoverable_energy_kwh'] for item in items]
                observed=[value for value in estimates if value is not None]
                check(f'queue:recovery_sort_{direction}',observed==sorted(observed,reverse=direction=='desc'))
                first_missing=next((index for index,value in enumerate(estimates) if value is None),len(estimates))
                check(f'queue:recovery_nulls_last_{direction}',all(value is None for value in estimates[first_missing:]))
                tied=[(left,right) for left,right in zip(items,items[1:])
                      if left['potential_recoverable_energy_kwh'] is not None
                      and left['potential_recoverable_energy_kwh']==right['potential_recoverable_energy_kwh']]
                check(f'queue:recovery_tie_break_{direction}',all(
                    (left['queue_position'],left['uc_id']) <= (right['queue_position'],right['uc_id'])
                    for left,right in tied
                ))
                estimates_by_uc={item['uc_id']:item['potential_recoverable_energy_kwh']
                                 for item in items if item['potential_recoverable_energy_kwh'] is not None}
                if estimates_by_uc:
                    db_estimates={row['id_uc']:row for row in db.execute(text(
                        'SELECT id_uc,energia_estimada_recuperavel_kwh,intervalo_recuperacao_inferior_kwh,'
                        'intervalo_recuperacao_superior_kwh,estado_estimativa_recuperacao,metodo_estimativa_recuperacao '
                        'FROM gold_v2.fila_inspecao WHERE id_uc = ANY(:ids)'
                    ),{'ids':list(estimates_by_uc)}).mappings()}
                    check(f'queue:recovery_values_match_sql_{direction}',all(
                        uc in db_estimates
                        and close(value,db_estimates[uc]['energia_estimada_recuperavel_kwh'])
                        and db_estimates[uc]['intervalo_recuperacao_inferior_kwh'] is not None
                        and db_estimates[uc]['intervalo_recuperacao_superior_kwh'] is not None
                        and db_estimates[uc]['intervalo_recuperacao_inferior_kwh'] <= value <= db_estimates[uc]['intervalo_recuperacao_superior_kwh']
                        and db_estimates[uc]['estado_estimativa_recuperacao']=='ESTIMATIVA_UC_POR_CONSUMO_SE_CONFIRMADA'
                        and db_estimates[uc]['metodo_estimativa_recuperacao']=='CONSUMO_CONDICIONAL_V1'
                        for uc,value in estimates_by_uc.items()
                    ))
                else:
                    check(f'queue:recovery_values_match_sql_{direction}',True)
            # Uma competência: recomputação direta dos numeradores/denominador.
            continuity=get('/operations/continuity?'+urllib.parse.urlencode({'periodo':month}))['data']
            expected={row['id_alimentador']:row for row in db.execute(text('SELECT id_alimentador,duracao_total_interrupcoes_horas,frequencia_total_interrupcoes,total_ucs_alimentador FROM gold_v2.indicadores_dec_fec WHERE competencia=:m'),{'m':month}).mappings()}
            check('operations:feeder_universe',set(expected)=={row['feeder_id'] for row in continuity})
            for index,point in enumerate(continuity):
                row=expected[point['feeder_id']]
                denominator=row['total_ucs_alimentador']
                check(f'operations:feeder_{index}_denominator',point['denominator_uc_count']==denominator)
                if denominator and denominator>0:
                    check(f'operations:feeder_{index}_dec',close(point['dec_hours_per_uc'],row['duracao_total_interrupcoes_horas']/denominator,'.0001'))
                    check(f'operations:feeder_{index}_fec',close(point['fec_interruptions_per_uc'],row['frequencia_total_interrupcoes']/denominator,'.0001'))
            db.rollback()
    except Exception as error:
        check('runner:'+type(error).__name__,False)
    finally:
        call('/auth/logout',{})
        engine.dispose()
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps({'publication':publication,'checks':checks},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    failed=[check['check'] for check in checks if not check['passed']]
    print(json.dumps({'checks':len(checks),'failed':failed}))
    return bool(failed)


if __name__=='__main__':
    raise SystemExit(main())
