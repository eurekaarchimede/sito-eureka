-- Migration: performance (bulk results) + sicurezza (validazione choice)
-- Esegui questo nel SQL Editor di Supabase DOPO le migrazioni precedenti.
-- Richiede che esistano già: motion_results, election_results, proposal_results.

-- ============================================================
-- #3 — RPC aggregate: una sola round-trip invece di N
-- ============================================================
-- Riusano le funzioni *_results esistenti (stessa logica/RLS),
-- ma collassano N richieste HTTP in una. Ritornano { id: json, ... }.

create or replace function public.bulk_motion_results(p_ids uuid[])
returns json
language sql stable security definer set search_path = public
as $$
  select coalesce(json_object_agg(t.id, public.motion_results(t.id)), '{}'::json)
  from unnest(p_ids) as t(id);
$$;
grant execute on function public.bulk_motion_results(uuid[]) to authenticated;

create or replace function public.bulk_election_results(p_ids uuid[])
returns json
language sql stable security definer set search_path = public
as $$
  select coalesce(json_object_agg(t.id, public.election_results(t.id)), '{}'::json)
  from unnest(p_ids) as t(id);
$$;
grant execute on function public.bulk_election_results(uuid[]) to authenticated;

create or replace function public.bulk_proposal_results(p_ids uuid[])
returns json
language sql stable security definer set search_path = public
as $$
  select coalesce(json_object_agg(t.id, public.proposal_results(t.id)), '{}'::json)
  from unnest(p_ids) as t(id);
$$;
grant execute on function public.bulk_proposal_results(uuid[]) to authenticated;

-- ============================================================
-- #5a — Validazione server-side di votes.choice
-- ============================================================
-- La migrazione custom-options ha droppato il CHECK su votes.choice.
-- Le RLS validano solo member_id + finestra temporale, NON il valore.
-- Questo trigger lo ripristina ed estende alle opzioni custom:
--   - mozione standard  -> choice in ('favorevole','contrario','astenuto')
--   - mozione custom    -> choice = any(options)
create or replace function public.validate_vote_choice()
returns trigger
language plpgsql security definer set search_path = public
as $$
declare
  opts text[];
begin
  select options into opts from public.motions where id = new.motion_id;
  if opts is null then
    if new.choice not in ('favorevole','contrario','astenuto') then
      raise exception 'invalid choice: %', new.choice;
    end if;
  elsif not (new.choice = any(opts)) then
    raise exception 'invalid choice: %', new.choice;
  end if;
  return new;
end;
$$;

drop trigger if exists trg_validate_vote_choice on public.votes;
create trigger trg_validate_vote_choice
  before insert or update on public.votes
  for each row execute function public.validate_vote_choice();
