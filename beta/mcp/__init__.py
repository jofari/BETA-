"""Le pont MCP : ce que BETA expose a un agent, et ce qu'il lui refuse.

Un banc d'essai branche sur un agent est une machine a multiplier les tests par mille. C'est
utile et c'est dangereux, dans cet ordre : le garde-fou n'est donc pas une option du serveur,
c'est sa raison d'etre. `beta_run_backtest` refuse un run sans preenregistrement, exactement
comme `contrats.Run` le refuse a un humain — un agent ne doit pas disposer d'un chemin que
Jonas n'a pas.
"""
