-- members_admin_all already grants administrators full access to the roster.
-- Remove the broader SELECT policy that exposed email/class to every active member.
drop policy if exists members_read on public.members;
