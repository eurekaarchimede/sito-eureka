# eureka! — contesto visivo

HTML/CSS/JavaScript vanilla; DM Sans; blu notte, oro e crema.

L’apertura dispone cielo, testo e facciata su livelli distinti. La scuola, più piccola, è nel flusso sotto i pulsanti; un render 3D con cornici e tetto in rilievo, una luce di base e una prospettiva allo scroll danno volume senza un ciclo WebGL aggiuntivo. Durante lo scroll l’edificio aumenta gradualmente di scala (fino a 1,22 su desktop e 1,14 su mobile), con una curva morbida e ancoraggio alla base per dare profondità senza invadere le scritte. La targa separata “ARCHIMEDE” è stata rimossa. Cielo, testo e scuola avanzano a velocità diverse durante lo scroll, anche nella modalità leggera; il movimento resta disattivato con “movimento ridotto”. Il tocco sulla scuola mostra un render 3D ritagliato della scena occupata, con gru, folla, bandiere, fumogeni e striscioni; un secondo tocco ripristina la facciata. Lo sfondo warp è ispirato a [HyperspaceWarpDrive](https://21st.dev/@dhileepkumargm/components/hyperspace-warp-drive), catalogo 7943, recuperato il 6 ottobre 2026. Si riutilizza il Canvas 2D esistente: nessun codice Three.js del componente importato.

Il campo HyperspaceWarpDrive riproduce i raggi prospettici 21st.dev su un solo Canvas 2D: persistenza dorata uniforme, accelerazione allo scroll su tutta la pagina, ritmo adattato a mobile e dispositivi a basso consumo. Niente Three.js extra o tracking del cursore; pausa in background e con movimento ridotto.

## Vortici blu e oro (7 ottobre 2026)

La texture del vecchio hero è stata reinterpretata in due WebP molto piccoli: 72 KB su mobile e 79 KB su desktop. Rimane visibile anche senza WebGL. Solo sui dispositivi capaci un canvas WebGL2 a bassa risoluzione anima brevemente i vortici: fino a 30 fotogrammi mobile o 100 desktop, poi si ferma. Telefoni con 2/4 GB dichiarati, risparmio dati e movimento ridotto usano direttamente la texture statica. Le stelle cadenti e il parallax della scuola mantengono i rispettivi limiti di lavoro.
