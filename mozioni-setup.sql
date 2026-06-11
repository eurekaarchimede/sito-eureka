-- ============================================================
-- eureka! mozioni — Supabase setup script
-- ============================================================
-- Esegui tutto lo script nel SQL Editor di Supabase (Run).
-- Idempotente: si può rieseguire senza danneggiare i dati.
-- ============================================================

create extension if not exists pgcrypto;
create extension if not exists citext;

-- ============================================================
-- TABELLE
-- ============================================================

create table if not exists public.members (
  id         uuid primary key default gen_random_uuid(),
  email      citext unique not null,
  name       text not null,
  role       text not null default 'member' check (role in ('admin','member')),
  active     boolean not null default true,
  created_at timestamptz not null default now()
);

create table if not exists public.motions (
  id          uuid primary key default gen_random_uuid(),
  title       text not null,
  description text,
  created_by  uuid references public.members(id) on delete set null,
  opens_at    timestamptz not null,
  closes_at   timestamptz not null,
  anonymous   boolean not null default false,
  created_at  timestamptz not null default now(),
  check (closes_at > opens_at)
);

create table if not exists public.votes (
  id         uuid primary key default gen_random_uuid(),
  motion_id  uuid not null references public.motions(id) on delete cascade,
  member_id  uuid not null references public.members(id) on delete cascade,
  choice     text not null check (choice in ('favorevole','contrario','astenuto')),
  created_at timestamptz not null default now(),
  unique (motion_id, member_id)
);

create index if not exists idx_motions_opens_at on public.motions (opens_at desc);
create index if not exists idx_votes_motion     on public.votes (motion_id);
create index if not exists idx_votes_member     on public.votes (member_id);

alter table public.members add column if not exists is_primary boolean not null default false;
alter table public.members add column if not exists classe text;

-- ============================================================
-- HELPERS
-- ============================================================

-- Restituisce la riga members corrispondente all'utente loggato.
-- Match via email (case-insensitive grazie a citext).
create or replace function public.current_member()
returns public.members
language sql stable security definer set search_path = public, auth
as $$
  select m.*
  from public.members m
  join auth.users u on u.email::citext = m.email
  where u.id = auth.uid() and m.active = true
  limit 1;
$$;

create or replace function public.is_admin()
returns boolean
language sql stable security definer set search_path = public
as $$
  select coalesce((select role = 'admin' from public.current_member()), false);
$$;

grant execute on function public.current_member() to authenticated;
grant execute on function public.is_admin()       to authenticated;

-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================

alter table public.members enable row level security;
alter table public.motions enable row level security;
alter table public.votes   enable row level security;

-- ---- members ----
drop policy if exists members_read       on public.members;
create policy members_read on public.members
  for select to authenticated
  using ((select id from public.current_member()) is not null);

drop policy if exists members_admin_all  on public.members;
create policy members_admin_all on public.members
  for all to authenticated
  using      (public.is_admin())
  with check (public.is_admin());

-- ---- motions ----
drop policy if exists motions_read       on public.motions;
create policy motions_read on public.motions
  for select to authenticated
  using ((select id from public.current_member()) is not null);

drop policy if exists motions_admin_all  on public.motions;
create policy motions_admin_all on public.motions
  for all to authenticated
  using      (public.is_admin())
  with check (public.is_admin());

-- ---- votes ----
-- I membri leggono solo i propri voti. L'admin legge tutto (per i risultati e backup).
drop policy if exists votes_read_own     on public.votes;
create policy votes_read_own on public.votes
  for select to authenticated
  using (member_id = (select id from public.current_member()));

drop policy if exists votes_admin_read   on public.votes;
create policy votes_admin_read on public.votes
  for select to authenticated
  using (public.is_admin());

-- Inserimento: solo se la mozione è aperta E si vota per sé stessi.
drop policy if exists votes_insert_own   on public.votes;
create policy votes_insert_own on public.votes
  for insert to authenticated
  with check (
    member_id = (select id from public.current_member())
    and exists (
      select 1 from public.motions m
      where m.id = motion_id
        and now() between m.opens_at and m.closes_at
    )
  );

-- Modifica: cambio voto entro la finestra di votazione.
drop policy if exists votes_update_own   on public.votes;
create policy votes_update_own on public.votes
  for update to authenticated
  using (
    member_id = (select id from public.current_member())
    and exists (
      select 1 from public.motions m
      where m.id = motion_id
        and now() between m.opens_at and m.closes_at
    )
  )
  with check (member_id = (select id from public.current_member()));

drop policy if exists votes_admin_all    on public.votes;
create policy votes_admin_all on public.votes
  for all to authenticated
  using      (public.is_admin())
  with check (public.is_admin());

-- ============================================================
-- RPC: motion_results
-- ============================================================
-- Restituisce i risultati di una mozione come JSON.
-- - Mozione aperta: admin → nomi e scelte di chi ha votato.
--                   membri → null (nessuna informazione finché non chiude).
-- - Mozione chiusa: counts sempre. Admin vede sempre nome→scelta.
--                   Membri: nominale → nome→scelta, anonima → solo turnout nomi.

create or replace function public.motion_results(p_motion_id uuid)
returns json
language plpgsql stable security definer set search_path = public
as $$
declare
  m       public.motions;
  cm      public.members;
  is_adm  boolean;
begin
  cm := public.current_member();
  if cm.id is null then return null; end if;

  select * into m from public.motions where id = p_motion_id;
  if m.id is null then return null; end if;

  is_adm := (cm.role = 'admin');

  -- mozione non ancora chiusa
  if now() < m.closes_at then
    if is_adm then
      return json_build_object(
        'closed', false,
        'anonymous', m.anonymous,
        'voters', (
          select coalesce(
            json_agg(json_build_object('name', mem.name, 'choice', v.choice) order by v.created_at),
            '[]'::json
          )
          from public.votes v
          join public.members mem on mem.id = v.member_id
          where v.motion_id = p_motion_id
        ),
        'total_voted',  (select count(*) from public.votes   where motion_id = p_motion_id),
        'total_voters', (select count(*) from public.members where active = true)
      );
    end if;
    return null;
  end if;

  -- mozione chiusa: admin vede sempre i dettagli dei voti
  return json_build_object(
    'closed', true,
    'anonymous', m.anonymous,
    'counts', coalesce((
      select json_object_agg(choice, c)
      from (
        select choice, count(*)::int as c
        from public.votes
        where motion_id = p_motion_id
        group by choice
      ) s
    ), '{}'::json),
    'voters', case when not m.anonymous or is_adm then (
        select coalesce(
          json_agg(json_build_object('name', mem.name, 'choice', v.choice) order by mem.name),
          '[]'::json
        )
        from public.votes v
        join public.members mem on mem.id = v.member_id
        where v.motion_id = p_motion_id
      )
      else null
    end,
    'turnout_names', case when m.anonymous and not is_adm then (
      select coalesce(json_agg(mem.name order by mem.name), '[]'::json)
      from public.votes v
      join public.members mem on mem.id = v.member_id
      where v.motion_id = p_motion_id
    ) else null end,
    'total_voted',  (select count(*) from public.votes   where motion_id = p_motion_id),
    'total_voters', (select count(*) from public.members where active = true)
  );
end;
$$;

grant execute on function public.motion_results(uuid) to authenticated;

-- ============================================================
-- RPC: check_registration + register_member
-- ============================================================

create or replace function public.check_registration(p_email text)
returns json
language plpgsql stable security definer set search_path = public, auth
as $$
declare
  m public.members;
  user_email citext;
begin
  user_email := (select email from auth.users where id = auth.uid())::citext;
  if user_email is null or user_email != p_email::citext then
    return null;
  end if;

  select * into m from public.members where email = p_email::citext;

  if m.id is null then
    return json_build_object('status', 'not_registered');
  end if;

  if not m.active then
    return json_build_object('status', 'pending', 'name', m.name);
  end if;

  return json_build_object(
    'status', 'active',
    'id', m.id,
    'name', m.name,
    'email', m.email,
    'role', m.role,
    'active', m.active,
    'is_primary', m.is_primary,
    'classe', m.classe
  );
end;
$$;

create or replace function public.register_member(p_name text, p_classe text)
returns json
language plpgsql security definer set search_path = public, auth
as $$
declare
  user_email citext;
  m public.members;
begin
  user_email := (select email from auth.users where id = auth.uid())::citext;
  if user_email is null then
    return json_build_object('error', 'not_authenticated');
  end if;

  select * into m from public.members where email = user_email;
  if m.id is not null then
    return json_build_object('error', 'already_registered');
  end if;

  insert into public.members (email, name, classe, role, active)
  values (user_email, p_name, p_classe, 'member', false)
  returning * into m;

  return json_build_object('status', 'pending', 'name', m.name);
end;
$$;

grant execute on function public.check_registration(text) to authenticated;
grant execute on function public.register_member(text, text) to authenticated;

-- ============================================================
-- TABLE GRANTS
-- ============================================================
-- Necessari perché il SQL Editor esegue come `postgres`, non come
-- `supabase_admin`, quindi i DEFAULT PRIVILEGES di Supabase non
-- si applicano automaticamente alle tabelle appena create.

grant select, insert, update, delete on public.members to authenticated;
grant select, insert, update, delete on public.motions to authenticated;
grant select, insert, update, delete on public.votes   to authenticated;

-- ============================================================
-- PROTEZIONE ADMIN PRIMARIO
-- ============================================================
create or replace function public.protect_primary_admin()
returns trigger
language plpgsql
as $$
begin
  if tg_op = 'DELETE' then
    if old.is_primary then
      raise exception 'impossibile eliminare admin primario';
    end if;
    return old;
  end if;
  if old.is_primary and (new.role != 'admin' or new.active = false or new.is_primary = false) then
    raise exception 'impossibile modificare admin primario';
  end if;
  return new;
end;
$$;

drop trigger if exists protect_primary on public.members;
create trigger protect_primary
  before update or delete on public.members
  for each row
  execute function public.protect_primary_admin();

-- ============================================================
-- BOOTSTRAP: primo admin (primario)
-- ============================================================
-- Cambia l'email se serve. La riga viene inserita solo se non esiste.

insert into public.members (email, name, role, is_primary)
values ('warmamiel@gmail.com', 'giacomo warm', 'admin', true)
on conflict (email) do update set role = 'admin', active = true, is_primary = true;

-- ============================================================
-- TABELLE ELEZIONI
-- ============================================================

create table if not exists public.elections (
  id          uuid primary key default gen_random_uuid(),
  title       text,
  organ       text not null check (organ in ('consiglio', 'garanzia')),
  seats       int  not null check (seats > 0),
  opens_at    timestamptz not null,
  closes_at   timestamptz not null,
  anonymous   boolean not null default false,
  created_by  uuid references public.members(id) on delete set null,
  created_at  timestamptz not null default now(),
  check (closes_at > opens_at)
);

create table if not exists public.election_votes (
  id           uuid primary key default gen_random_uuid(),
  election_id  uuid not null references public.elections(id) on delete cascade,
  voter_id     uuid not null references public.members(id) on delete cascade,
  candidate_id uuid not null references public.members(id) on delete cascade,
  created_at   timestamptz not null default now(),
  unique (election_id, voter_id, candidate_id)
);

create index if not exists idx_elections_opens_at on public.elections (opens_at desc);
create index if not exists idx_evotes_election    on public.election_votes (election_id);
create index if not exists idx_evotes_voter       on public.election_votes (voter_id);
create index if not exists idx_evotes_candidate   on public.election_votes (candidate_id);

alter table public.elections      enable row level security;
alter table public.election_votes enable row level security;

-- ---- elections ----
drop policy if exists elections_read     on public.elections;
create policy elections_read on public.elections
  for select to authenticated
  using ((select id from public.current_member()) is not null);

drop policy if exists elections_admin_all on public.elections;
create policy elections_admin_all on public.elections
  for all to authenticated
  using      (public.is_admin())
  with check (public.is_admin());

-- ---- election_votes ----
drop policy if exists evotes_read_own   on public.election_votes;
create policy evotes_read_own on public.election_votes
  for select to authenticated
  using (voter_id = (select id from public.current_member()));

drop policy if exists evotes_admin_read on public.election_votes;
create policy evotes_admin_read on public.election_votes
  for select to authenticated
  using (public.is_admin());

drop policy if exists evotes_admin_all  on public.election_votes;
create policy evotes_admin_all on public.election_votes
  for all to authenticated
  using      (public.is_admin())
  with check (public.is_admin());

grant select, insert, update, delete on public.elections      to authenticated;
grant select, insert, update, delete on public.election_votes to authenticated;

-- ============================================================
-- RPC: election_results
-- ============================================================
create or replace function public.election_results(p_election_id uuid)
returns json
language plpgsql stable security definer set search_path = public
as $$
declare
  cm      public.members;
  el      public.elections;
  is_adm  boolean;
  is_open boolean;
begin
  cm := public.current_member();
  if cm.id is null then return null; end if;

  select * into el from public.elections where id = p_election_id;
  if el.id is null then return null; end if;

  is_adm  := (cm.role = 'admin');
  is_open := (now() between el.opens_at and el.closes_at);

  return json_build_object(
    'closed',    not is_open and now() > el.closes_at,
    'organ',     el.organ,
    'seats',     el.seats,
    'anonymous', el.anonymous,
    'my_votes', (
      select coalesce(json_agg(candidate_id), '[]'::json)
      from public.election_votes
      where election_id = p_election_id and voter_id = cm.id
    ),
    'candidates', (
      select coalesce(json_agg(
        json_build_object(
          'id',     m.id,
          'name',   m.name,
          'classe', m.classe,
          'votes',  case when is_adm then coalesce(vc.cnt, 0) else null end,
          'voters', case when is_adm then (
              select coalesce(json_agg(vm.name order by vm.name), '[]'::json)
              from public.election_votes ev2
              join public.members vm on vm.id = ev2.voter_id
              where ev2.election_id = p_election_id and ev2.candidate_id = m.id
            ) else null end
        ) order by
          case when is_adm then coalesce(vc.cnt, 0) else 0 end desc,
          m.name asc
      ), '[]'::json)
      from public.members m
      left join (
        select candidate_id, count(*)::int as cnt
        from public.election_votes
        where election_id = p_election_id
        group by candidate_id
      ) vc on vc.candidate_id = m.id
      where m.active = true
    ),
    'total_voted',  case when is_adm then (select count(distinct voter_id)::int from public.election_votes where election_id = p_election_id) else null end,
    'total_voters', case when is_adm then (select count(*)::int from public.members where active = true) else null end
  );
end;
$$;

-- ============================================================
-- RPC: cast_election_vote
-- ============================================================
create or replace function public.cast_election_vote(
  p_election_id   uuid,
  p_candidate_ids uuid[]
)
returns json
language plpgsql security definer set search_path = public
as $$
declare
  cm  public.members;
  el  public.elections;
  n   int;
begin
  cm := public.current_member();
  if cm.id is null then return json_build_object('error', 'not_authenticated'); end if;

  select * into el from public.elections where id = p_election_id;
  if el.id is null then return json_build_object('error', 'not_found'); end if;

  if not (now() between el.opens_at and el.closes_at) then
    return json_build_object('error', 'not_open');
  end if;

  n := coalesce(cardinality(p_candidate_ids), 0);
  if n > el.seats then
    return json_build_object('error', 'too_many', 'max', el.seats);
  end if;

  if n > 0 and exists (
    select 1 from unnest(p_candidate_ids) as t(cid)
    where not exists (
      select 1 from public.members where id = t.cid and active = true
    )
  ) then
    return json_build_object('error', 'invalid_candidate');
  end if;

  delete from public.election_votes
  where election_id = p_election_id and voter_id = cm.id;

  if n > 0 then
    insert into public.election_votes (election_id, voter_id, candidate_id)
    select p_election_id, cm.id, unnest(p_candidate_ids);
  end if;

  return json_build_object('ok', true, 'count', n);
end;
$$;

grant execute on function public.election_results(uuid)            to authenticated;
grant execute on function public.cast_election_vote(uuid, uuid[])  to authenticated;

-- ============================================================
-- FINE
-- ============================================================
-- Dopo aver eseguito tutto:
--   1. Vai in Authentication → URL Configuration e imposta:
--        - Site URL: l'URL pubblico dove servirai mozioni.html
--        - Redirect URLs: aggiungi lo stesso URL (e localhost se sviluppi in locale)
--   2. Project Settings → API: copia "Project URL" e "anon public" key.
--   3. Apri mozioni.html, sostituisci le costanti SUPABASE_URL e SUPABASE_ANON_KEY.
-- ============================================================
