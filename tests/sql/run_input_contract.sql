-- Run only in a disposable database after all Supabase migrations.
-- The enclosing transaction leaves no fixtures behind.
begin;
insert into public.tickers(symbol,market) values ('SEAL_TEST','US');
insert into public.analysis_runs(id,symbol,as_of_date,status) values
('00000000-0000-0000-0000-000000000001','SEAL_TEST','2026-10-08','running');
insert into public.analysis_run_inputs(run_id,symbol,as_of_date,payload,input_hash) values
('00000000-0000-0000-0000-000000000001','SEAL_TEST','2026-10-08','{}',repeat('a',64));
insert into public.analysis_artifacts(run_id,symbol,as_of_date,stage,schema_version,payload,input_hash) values
('00000000-0000-0000-0000-000000000001','SEAL_TEST','2026-10-08','analyst_reports',2,'{}',repeat('a',64));
do $$
begin
    if has_table_privilege('anon','public.analysis_run_inputs','select')
       or has_table_privilege('authenticated','public.analysis_run_inputs','select') then
        raise exception 'Raw seals must not be public';
    end if;
    if has_table_privilege('service_role','public.analysis_run_inputs','update')
       or has_table_privilege('service_role','public.analysis_run_inputs','delete') then
        raise exception 'Default privileges leaked mutation rights';
    end if;
    if not has_table_privilege('service_role','public.analysis_run_inputs','insert')
       or not has_table_privilege('service_role','public.analysis_run_inputs','select') then
        raise exception 'Worker cannot seal/resume';
    end if;
    begin
        update public.analysis_run_inputs set payload='{"changed":true}';
        raise exception 'Update unexpectedly succeeded';
    exception when raise_exception then
        if sqlerrm <> 'analysis run input is immutable' then raise; end if;
    end;
    begin
        update public.analysis_artifacts set input_hash=repeat('b',64);
        raise exception 'Mismatched hash unexpectedly succeeded';
    exception when foreign_key_violation then null;
    end;
    begin
        update public.analysis_artifacts set input_hash=null;
        raise exception 'Version 2 null hash unexpectedly succeeded';
    exception when check_violation then null;
    end;
end;
$$;
-- Completed legacy artifacts remain readable and require no invented seal.
insert into public.analysis_artifacts(run_id,symbol,as_of_date,stage,schema_version,payload) values
('00000000-0000-0000-0000-000000000001','SEAL_TEST','2026-10-08','briefing',1,'{}');
rollback;
