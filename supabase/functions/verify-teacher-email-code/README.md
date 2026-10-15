# Verifica del codice email docenti

La funzione non conserva il codice nel repository e non accede alla chiave REST di OneSignal. Verifica il codice condiviso e restituisce `verified: true`; il sito procede poi con `OneSignal.User.addEmail()`.

Prima di pubblicare la modifica al sito, impostare nel progetto Supabase `awdsasbjuueovjcupmwk` il secret `TEACHER_EMAIL_PASSWORD` (almeno 12 caratteri) da **Project Settings → Edge Functions → Secrets**. Il valore deve restare fuori da GitHub, dal sorgente HTML e dai messaggi. La funzione viene pubblicata con `verify_jwt` disattivato perché il sito statico non usa account Supabase; la funzione applica invece il controllo del codice e dell'origine.

Verifica dal sito: inserire un indirizzo, il codice corretto e il consenso; il messaggio di successo deve apparire solo dopo la conferma di `addEmail()` da parte di OneSignal. Un codice errato deve lasciare i campi compilati e mostrare un errore.
