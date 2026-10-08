@echo off
chcp 65001 > nul
title VPS - tunnel SSH vers les dashboards (laisser cette fenetre ouverte)
rem Les dashboards du VPS n'ecoutent que sur le VPS lui-meme (127.0.0.1) : rien n'est expose
rem a Internet. Ce tunnel SSH les amene sur ce PC tant que cette fenetre reste ouverte :
rem   http://127.0.0.1:7580            tableau de bord du VPS (etat, marche, liquidations, news)
rem   http://127.0.0.1:7574/#forward   BETA sur le VPS : suivis et paper des trois voies C
rem Ports 75xx et non 74xx : le BETA local de ce PC garde le 7474.
rem Si le navigateur s'ouvre avant la fin de la connexion, rafraichir la page.
set VPS=root@76.13.62.171
echo Tunnel vers %VPS% ... (le mot de passe SSH est demande ici si tu n'as pas de cle)
start "" /b cmd /c "timeout /t 6 /nobreak > nul & start "" http://127.0.0.1:7580 & start "" http://127.0.0.1:7574/#forward"
ssh -N -o ServerAliveInterval=30 -o ExitOnForwardFailure=yes -L 7580:127.0.0.1:7480 -L 7574:127.0.0.1:7474 %VPS%
echo.
echo Tunnel ferme. Si ce n'etait pas voulu, lire le message ci-dessus.
pause
