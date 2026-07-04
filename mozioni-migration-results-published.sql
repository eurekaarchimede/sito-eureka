-- Migration: results_published su motions
-- Esegui questo nel SQL Editor di Supabase

-- 1. Aggiungi colonna
ALTER TABLE public.motions ADD COLUMN IF NOT EXISTS results_published boolean NOT NULL DEFAULT false;

-- 2. Aggiorna motion_results: non-admin vede risultati solo se pubblicati
CREATE OR REPLACE FUNCTION public.motion_results(p_motion_id uuid)
RETURNS json
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public
AS $$
DECLARE
  m       public.motions;
  cm      public.members;
  is_adm  boolean;
BEGIN
  cm := public.current_member();
  IF cm.id IS NULL THEN RETURN NULL; END IF;

  SELECT * INTO m FROM public.motions WHERE id = p_motion_id;
  IF m.id IS NULL THEN RETURN NULL; END IF;

  is_adm := (cm.role = 'admin');

  -- mozione non ancora chiusa
  IF now() < m.closes_at THEN
    IF is_adm THEN
      RETURN json_build_object(
        'closed', false,
        'anonymous', m.anonymous,
        'voters', (
          SELECT coalesce(
            json_agg(json_build_object('name', mem.name, 'choice', v.choice) ORDER BY v.created_at),
            '[]'::json
          )
          FROM public.votes v
          JOIN public.members mem ON mem.id = v.member_id
          WHERE v.motion_id = p_motion_id
        ),
        'total_voted',  (SELECT count(*) FROM public.votes   WHERE motion_id = p_motion_id),
        'total_voters', (SELECT count(*) FROM public.members WHERE active = TRUE)
      );
    END IF;
    RETURN NULL;
  END IF;

  -- mozione chiusa: non-admin vede risultati solo se pubblicati
  IF NOT is_adm AND NOT m.results_published THEN
    RETURN json_build_object('closed', TRUE, 'not_published', TRUE, 'anonymous', m.anonymous);
  END IF;

  RETURN json_build_object(
    'closed', TRUE,
    'anonymous', m.anonymous,
    'counts', coalesce((
      SELECT json_object_agg(choice, c)
      FROM (
        SELECT choice, count(*)::int AS c
        FROM public.votes
        WHERE motion_id = p_motion_id
        GROUP BY choice
      ) s
    ), '{}'::json),
    'voters', CASE WHEN NOT m.anonymous OR is_adm THEN (
        SELECT coalesce(
          json_agg(json_build_object('name', mem.name, 'choice', v.choice) ORDER BY mem.name),
          '[]'::json
        )
        FROM public.votes v
        JOIN public.members mem ON mem.id = v.member_id
        WHERE v.motion_id = p_motion_id
      )
      ELSE NULL
    END,
    'turnout_names', CASE WHEN m.anonymous AND NOT is_adm THEN (
      SELECT coalesce(json_agg(mem.name ORDER BY mem.name), '[]'::json)
      FROM public.votes v
      JOIN public.members mem ON mem.id = v.member_id
      WHERE v.motion_id = p_motion_id
    ) ELSE NULL END,
    'total_voted',  (SELECT count(*) FROM public.votes   WHERE motion_id = p_motion_id),
    'total_voters', (SELECT count(*) FROM public.members WHERE active = TRUE)
  );
END;
$$;
