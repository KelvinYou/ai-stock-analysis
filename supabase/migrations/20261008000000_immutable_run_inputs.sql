-- Service-only immutable inputs. Completed legacy artifacts remain readable.
create table public.analysis_run_inputs (
    run_id uuid primary key references public.analysis_runs(id) on delete cascade,
    symbol text not null references public.tickers(symbol),
    as_of_date date not null,
    payload jsonb not null,
    input_hash text not null check (input_hash ~ '^[0-9a-f]{64}$'),
    created_at timestamptz not null default now(),
    unique (run_id, input_hash)
);
alter table public.analysis_run_inputs enable row level security;
revoke all on public.analysis_run_inputs from public, anon, authenticated, service_role;
grant select, insert on public.analysis_run_inputs to service_role;

create function public.reject_run_input_update() returns trigger
language plpgsql set search_path = public as $$
begin
    raise exception 'analysis run input is immutable';
end;
$$;
create trigger immutable_analysis_run_input before update on public.analysis_run_inputs
for each row execute function public.reject_run_input_update();

alter table public.analysis_artifacts add column input_hash text
    check (input_hash is null or input_hash ~ '^[0-9a-f]{64}$');

-- Legacy rows have null hashes; newly sealed stages require the exact parent seal.
alter table public.analysis_artifacts
    add constraint analysis_artifact_sealed_input_fk foreign key (run_id, input_hash)
        references public.analysis_run_inputs(run_id, input_hash),
    add constraint analysis_artifact_v2_requires_input_hash
        check (schema_version < 2 or input_hash is not null);
