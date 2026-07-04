-- Migration: candidate_ids per election
-- Esegui questo nel SQL Editor di Supabase

-- 1. Aggiungi colonna
ALTER TABLE public.elections ADD COLUMN IF NOT EXISTS candidate_ids uuid[];

-- 2. Aggiorna election_results (filtra candidati per elezione)
CREATE OR REPLACE FUNCTION public.election_results(p_election_id uuid)
RETURNS json
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public
AS $$
DECLARE
  cm      public.members;
  el      public.elections;
  is_adm  boolean;
  is_open boolean;
BEGIN
  cm := public.current_member();
  IF cm.id IS NULL THEN RETURN NULL; END IF;

  SELECT * INTO el FROM public.elections WHERE id = p_election_id;
  IF el.id IS NULL THEN RETURN NULL; END IF;

  is_adm  := (cm.role = 'admin');
  is_open := (now() BETWEEN el.opens_at AND el.closes_at);

  RETURN json_build_object(
    'closed',    NOT is_open AND now() > el.closes_at,
    'organ',     el.organ,
    'seats',     el.seats,
    'anonymous', el.anonymous,
    'my_votes', (
      SELECT coalesce(json_agg(candidate_id), '[]'::json)
      FROM public.election_votes
      WHERE election_id = p_election_id AND voter_id = cm.id
    ),
    'candidates', (
      SELECT coalesce(json_agg(
        json_build_object(
          'id',     m.id,
          'name',   m.name,
          'classe', m.classe,
          'votes',  CASE WHEN is_adm THEN coalesce(vc.cnt, 0) ELSE NULL END,
          'voters', CASE WHEN is_adm THEN (
              SELECT coalesce(json_agg(vm.name ORDER BY vm.name), '[]'::json)
              FROM public.election_votes ev2
              JOIN public.members vm ON vm.id = ev2.voter_id
              WHERE ev2.election_id = p_election_id AND ev2.candidate_id = m.id
            ) ELSE NULL END
        ) ORDER BY
          CASE WHEN is_adm THEN coalesce(vc.cnt, 0) ELSE 0 END DESC,
          m.name ASC
      ), '[]'::json)
      FROM public.members m
      LEFT JOIN (
        SELECT candidate_id, count(*)::int AS cnt
        FROM public.election_votes
        WHERE election_id = p_election_id
        GROUP BY candidate_id
      ) vc ON vc.candidate_id = m.id
      WHERE m.active = TRUE
        AND (el.candidate_ids IS NULL OR m.id = ANY(el.candidate_ids))
    ),
    'total_voted',  CASE WHEN is_adm THEN (SELECT count(DISTINCT voter_id)::int FROM public.election_votes WHERE election_id = p_election_id) ELSE NULL END,
    'total_voters', CASE WHEN is_adm THEN (SELECT count(*)::int FROM public.members WHERE active = TRUE) ELSE NULL END
  );
END;
$$;

-- 3. Aggiorna cast_election_vote (valida che i candidati scelti siano nella lista)
CREATE OR REPLACE FUNCTION public.cast_election_vote(
  p_election_id   uuid,
  p_candidate_ids uuid[]
)
RETURNS json
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public
AS $$
DECLARE
  cm  public.members;
  el  public.elections;
  n   int;
BEGIN
  cm := public.current_member();
  IF cm.id IS NULL THEN RETURN json_build_object('error', 'not_authenticated'); END IF;

  SELECT * INTO el FROM public.elections WHERE id = p_election_id;
  IF el.id IS NULL THEN RETURN json_build_object('error', 'not_found'); END IF;

  IF NOT (now() BETWEEN el.opens_at AND el.closes_at) THEN
    RETURN json_build_object('error', 'not_open');
  END IF;

  n := coalesce(cardinality(p_candidate_ids), 0);
  IF n > el.seats THEN
    RETURN json_build_object('error', 'too_many', 'max', el.seats);
  END IF;

  IF n > 0 AND EXISTS (
    SELECT 1 FROM unnest(p_candidate_ids) AS t(cid)
    WHERE NOT EXISTS (
      SELECT 1 FROM public.members WHERE id = t.cid AND active = TRUE
      AND (el.candidate_ids IS NULL OR t.cid = ANY(el.candidate_ids))
    )
  ) THEN
    RETURN json_build_object('error', 'invalid_candidate');
  END IF;

  DELETE FROM public.election_votes
  WHERE election_id = p_election_id AND voter_id = cm.id;

  IF n > 0 THEN
    INSERT INTO public.election_votes (election_id, voter_id, candidate_id)
    SELECT p_election_id, cm.id, unnest(p_candidate_ids);
  END IF;

  RETURN json_build_object('ok', TRUE, 'count', n);
END;
$$;
