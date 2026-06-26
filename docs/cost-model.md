# Modele de cout Cloud Lab

## Position production

Cloud Lab utilise un modele de cout interne tant qu'une API billing Infomaniak exploitable n'est pas branchee.

Le cout affiche n'est donc pas une facture fournisseur. C'est une estimation operationnelle fiable basee sur :

- le prix horaire du template VM (`vm_templates.estimated_cost_per_hour_chf`) ;
- la duree reelle de vie de la VM ;
- la date de destruction effective quand elle existe ;
- le fuseau horaire suisse (`Europe/Zurich`) pour les regroupements journaliers.

## Calcul

Pour chaque VM :

```text
cout = heures_d_execution_reelles * prix_horaire_template
```

La duree est calculee depuis `virtual_machines.created_at` jusqu'a :

- `virtual_machines.destroyed_at` si la VM est detruite ;
- l'heure courante si la VM est encore active ;
- zero si la VM est en erreur sans duree exploitable.

Les lignes journalieres sont stockees dans `cost_records`.

## Limite connue

Ce modele ne remplace pas une facture Infomaniak. Pour une production complete avec billing fournisseur, il faudra ajouter un connecteur dedie si Infomaniak expose une API de consommation/couts par projet.

Dans ce cas, le backend devra garder le modele interne comme fallback et ajouter une source `provider_billing` pour comparer :

- cout interne estime ;
- cout facture fournisseur ;
- ecart eventuel.
