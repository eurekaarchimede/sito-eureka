-- Migration: raccolta proposte + mozioni a scelta multipla
-- Esegui nel SQL Editor di Supabase

-- ============================================================
-- 1. Mozioni a scelta multipla: colonna options
-- ============================================================
ALTER TABLE public.motions ADD COLUMN IF NOT EXISTS options text[];

-- Rimuovi il check su votes.choice per permettere opzioni custom
DO $$
DECLARE
  cname text;
BEGIN
  SELECT tc.constraint_name INTO cname
  FROM information_schema.table_constraints tc
  JOIN information_schema.check_constraints cc
    ON cc.constraint_name = tc.constraint_name
    AND cc.constraint_schema = tc.constraint_schema
  WHERE tc.table_name = 'votes'
    AND tc.table_schema = 'public'
    AND tc.constraint_type = 'CHECK'
    AND cc.check_clause LIKE '%favorevole%'
  LIMIT 1;
  IF cname IS NOT NULL THEN
    EXECUTE format('ALTER TABLE public.votes DROP CONSTRAINT %I', cname);
  END IF;
END
$$;

-- ============================================================
-- 2. Tabella proposals (raccolte proposte)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.proposals (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title        text NOT NULL,
  description  text,
  opens_at     timestamptz NOT NULL,
  closes_at    timestamptz NOT NULL,
  created_by   uuid REFERENCES public.members(id) ON DELETE SET NULL,
  created_at   timestamptz NOT NULL DEFAULT now(),
  CHECK (closes_at > opens_at)
);

ALTER TABLE public.proposals ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS proposals_read     ON public.proposals;
CREATE POLICY proposals_read ON public.proposals
  FOR SELECT TO authenticated
  USING ((SELECT id FROM public.current_member()) IS NOT NULL);

DROP POLICY IF EXISTS proposals_admin_all ON public.proposals;
CREATE POLICY proposals_admin_all ON public.proposals
  FOR ALL TO authenticated
  USING      (public.is_admin())
  WITH CHECK (public.is_admin());

GRANT SELECT, INSERT, UPDATE, DELETE ON public.proposals TO authenticated;

-- ============================================================
-- 3. Tabella proposal_responses
-- ============================================================
CREATE TABLE IF NOT EXISTS public.proposal_responses (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  proposal_id  uuid NOT NULL REFERENCES public.proposals(id) ON DELETE CASCADE,
  member_id    uuid NOT NULL REFERENCES public.members(id)   ON DELETE CASCADE,
  text         text NOT NULL,
  created_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (proposal_id, member_id)
);

ALTER TABLE public.proposal_responses ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS presp_read      ON public.proposal_responses;
CREATE POLICY presp_read ON public.proposal_responses
  FOR SELECT TO authenticated
  USING (
    member_id = (SELECT id FROM public.current_member())
    OR public.is_admin()
  );

DROP POLICY IF EXISTS presp_admin_all ON public.proposal_responses;
CREATE POLICY presp_admin_all ON public.proposal_responses
  FOR ALL TO authenticated
  USING      (public.is_admin())
  WITH CHECK (public.is_admin());

GRANT SELECT, INSERT, UPDATE, DELETE ON public.proposal_responses TO authenticated;

-- ============================================================
-- 4. RPC: submit_proposal_response
-- ============================================================
CREATE OR REPLACE FUNCTION public.submit_proposal_response(
  p_proposal_id uuid,
  p_text        text
)
RETURNS json
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public
AS $$
DECLARE
  cm  public.members;
  pr  public.proposals;
BEGIN
  cm := public.current_member();
  IF cm.id IS NULL THEN RETURN json_build_object('error', 'not_authenticated'); END IF;

  SELECT * INTO pr FROM public.proposals WHERE id = p_proposal_id;
  IF pr.id IS NULL THEN RETURN json_build_object('error', 'not_found'); END IF;

  IF NOT (now() BETWEEN pr.opens_at AND pr.closes_at) THEN
    RETURN json_build_object('error', 'not_open');
  END IF;

  INSERT INTO public.proposal_responses (proposal_id, member_id, text)
  VALUES (p_proposal_id, cm.id, p_text)
  ON CONFLICT (proposal_id, member_id)
  DO UPDATE SET text = EXCLUDED.text, created_at = now();

  RETURN json_build_object('ok', true);
END;
$$;

GRANT EXECUTE ON FUNCTION public.submit_proposal_response(uuid, text) TO authenticated;

-- ============================================================
-- 5. RPC: proposal_results
-- ============================================================
CREATE OR REPLACE FUNCTION public.proposal_results(p_proposal_id uuid)
RETURNS json
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public
AS $$
DECLARE
  cm     public.members;
  pr     public.proposals;
  is_adm boolean;
BEGIN
  cm := public.current_member();
  IF cm.id IS NULL THEN RETURN NULL; END IF;

  SELECT * INTO pr FROM public.proposals WHERE id = p_proposal_id;
  IF pr.id IS NULL THEN RETURN NULL; END IF;

  is_adm := (cm.role = 'admin');

  IF is_adm THEN
    RETURN json_build_object(
      'my_response', (
        SELECT text FROM public.proposal_responses
        WHERE proposal_id = p_proposal_id AND member_id = cm.id
        LIMIT 1
      ),
      'responses', (
        SELECT coalesce(json_agg(
          json_build_object('name', m.name, 'text', r.text, 'created_at', r.created_at)
          ORDER BY r.created_at
        ), '[]'::json)
        FROM public.proposal_responses r
        JOIN public.members m ON m.id = r.member_id
        WHERE r.proposal_id = p_proposal_id
      ),
      'total', (SELECT count(*)::int FROM public.proposal_responses WHERE proposal_id = p_proposal_id)
    );
  ELSE
    RETURN json_build_object(
      'my_response', (
        SELECT text FROM public.proposal_responses
        WHERE proposal_id = p_proposal_id AND member_id = cm.id
        LIMIT 1
      ),
      'total', (SELECT count(*)::int FROM public.proposal_responses WHERE proposal_id = p_proposal_id)
    );
  END IF;
END;
$$;

GRANT EXECUTE ON FUNCTION public.proposal_results(uuid) TO authenticated;
