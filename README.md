# Coleção do MTG Arena (ferramenta não oficial)

Transforma a coleção de cartas do MTG Arena que o mtga-mcp guarda no seu Mac num CSV com os
dados de cada carta e monta decks com as cartas que você tem, sem pagar por tracker.

Feito por um jogador, de graça. Não tem vínculo com a Wizards of the Coast, dona do Magic e do
MTG Arena. Veja o [aviso legal](#aviso-legal).

## O que este projeto não faz

- **Não lê a memória do jogo e não automatiza nada nele.** Só lê arquivos que o jogo grava no
  seu Mac: o banco de cartas que ele baixa e, pelo mtga-mcp, os logs detalhados.
- **Não acessa a internet** e não pede a sua senha.

Os [Termos de Uso da Wizards](https://company.wizards.com/en/legal/terms) (seção 2.2) não
permitem programas não autorizados que leem dados dos jogos. A Wizards cita as ferramentas da
comunidade que leem os logs na própria
[página de suporte do MTG Arena](https://mtgarena-support.wizards.com/hc/en-us/articles/360000726823-Creating-Log-Files),
mas não diz nada parecido sobre ler a memória do jogo, então essa parte ficou de fora.

## Como funciona

- **Catálogo de cartas**: lido do banco que o próprio jogo baixa em
  `~/Library/Application Support/com.wizards.mtga/Downloads/Raw/Raw_CardDatabase_*.mtga`.
  Dá nome em inglês e português, coleção, número, raridade, custo de mana, cores, linha de tipo
  e texto de regras de cada carta, pelo id que o Arena usa. O projeto lê esse arquivo no seu
  computador e não copia nada dele para cá.
- **Coleção**: fica no banco do [mtga-mcp](https://github.com/fkadriver/mtga-mcp), uma
  ferramenta aberta de outra pessoa. Com os logs detalhados ligados, o `mtga-mcp capture` lê nos
  logs do jogo as cartas que você ganha (pacotes, recompensas, cartas criadas com curinga) e soma
  à coleção.
- **Limite**: desde 2021 o jogo não grava mais nos logs a lista completa das suas cartas. Pelos
  logs, a coleção começa vazia e cresce com o que você ganhar a partir daí.
- **CSV**: `exports/collection.csv` tem uma linha por impressão de carta, com as colunas
  `quantity`, `name`, `portuguese_name`, `set_code`, `collector_number`, `rarity`, `mana_cost`,
  `mana_value`, `colors`, `color_identity`, `type_line`, `power`, `toughness`, `rules_text`,
  `mechanics`, `arena_id`, `digital_release_set`, `is_digital_only` e `is_rebalanced`. Cada
  mudança de quantidade também entra em `exports/collection-changes.csv`, com data, carta,
  quantidade anterior e nova.
- **Mecânicas**: a coluna `mechanics` traz etiquetas lidas do texto da carta, separadas por
  ponto e vírgula, como `ganho-de-vida`, `ganho-de-vida-recompensa`, `fichas`, `sacrificio`,
  `remocao` ou `tribo:goblin`. Os temas vêm em par: quem faz (`ganho-de-vida`) e quem é
  recompensado por isso (`ganho-de-vida-recompensa`). A lista completa, com a descrição de cada
  etiqueta, está em `src/mtg_arena_collection/card_mechanics.py`.

## Começar

Precisa de um Mac com o MTG Arena instalado, Python 3.10 ou mais novo (o `python3` do sistema é
3.9, então use o do Homebrew) e o mtga-mcp.

1. Instale o mtga-mcp seguindo o README dele, em `~/Developer/mtga-mcp`. O programa é de outra
   pessoa: leia o código antes e fique num commit que você revisou. Se ele estiver em outra
   pasta, passe `--mtga-mcp` com o caminho do executável.
2. Na pasta do mtga-mcp, importe o catálogo de cartas e a legalidade de cada formato:

   ```bash
   uv run mtga-mcp import --catalog
   uv run mtga-mcp import --scryfall
   ```

3. No jogo, ligue os logs detalhados em Opções → Account → **Detailed Logs (Plugin Support)** e
   reinicie o jogo.
4. Gere o CSV com as cartas que os logs mostram:

   ```bash
   ./scripts/refresh-collection.sh
   ```

Para refazer o CSV a partir do que já está no banco do mtga-mcp, sem ler os logs, use
`./scripts/import-from-mtga-mcp.sh`.

## Atualização automática

Com os logs detalhados ligados, instale o agendamento uma vez:

```bash
./scripts/install-automatic-refresh.sh
```

Ele roda `scripts/refresh-collection.sh` a cada 5 minutos pelo launchd:

- **Logs sem mudança**: não faz nada.
- **Carta nova**: atualiza o CSV e registra a mudança.

As execuções que mudam algo ou dão erro ficam registradas em
`~/Library/Logs/mtg-arena-collection/refresh.log`. O agendamento procura o mtga-mcp em
`~/Developer/mtga-mcp`. Para remover:

```bash
./scripts/uninstall-automatic-refresh.sh
```

Os logs deste Mac só mostram o que acontece no jogo deste Mac. Cartas ganhas em outro aparelho
não entram.

## Pasta de decks

Todo deck montado aqui fica em `decks/<formato>/<cores>/<tipo>/<nome-do-deck>.txt`, por
exemplo `decks/historic-brawl/mono-red/goblins/krenko-goblins.txt`. As cores usam os nomes de
sempre do Magic: mono-red, izzet (azul e vermelho), esper (branco, azul e preto) e assim por
diante. A pasta fica fora do git, porque os decks são seus.

Cada arquivo está no formato que o MTG Arena importa: copie o conteúdo e, no jogo, vá em
Decks → Importar. O formato do deck você escolhe no Arena depois de importar.

Para guardar um deck montado no Arena, use Exportar no jogo, que copia a lista, e rode:

```bash
pbpaste | ./scripts/save-deck.sh --name "Krenko Goblins" --format "Historic Brawl" --archetype Goblins
```

As cores saem das cartas: no Brawl, da identidade do comandante. Para escolher outras, use
`--colors` com as letras WUBRG.

## O que o meta ensina

Os decks do meta ficam no banco do mtga-mcp, que os importa de sites de decks com
`mtga-mcp deck bulk-import` (por exemplo a lista dos mais jogados e a dos melhores resultados
do AetherHub, em Bo1). As listas são desses sites: confira os termos de cada um antes de
importar. Para aprender com elas, rode:

```bash
./scripts/learn-from-meta.sh
```

O comando grava duas coisas em `exports/meta-lessons/`:

- `meta-lessons.md`: relatório por formato. Mostra quantos terrenos os decks jogam conforme o
  custo médio das mágicas, a curva e os papéis (criaturas, remoção, compra, rampa, anula) por
  velocidade e por mecânica, as cartas mais jogadas em cada mecânica e os pares de mecânicas e de
  cartas que aparecem juntos mais do que o acaso.
- `meta-lessons.json`: os mesmos números, para consultar em outros programas.

Cada deck pesa conforme se destaca na própria lista: a fatia do meta (ou o win rate) dividida
pela média da lista. As contagens são por 60 cartas, ou 99 no Historic Brawl.

Por enquanto a análise vale para uma importação só. Importar o meta de novo no mtga-mcp soma os
decks novos aos antigos, sem apagar nada.

## Desenhar decks

O designer monta decks só com cartas que você tem e que são legais no formato. Cada deck gira em
torno de um motor: uma mecânica em uma ou duas cores, ou um comandante no Brawl. Para ele
sugerir os motores que a sua coleção sustenta:

```bash
./scripts/design-decks.sh --format Standard
```

Ou escolha o motor. `--include` põe cartas obrigatórias, como as peças de um combo:

```bash
./scripts/design-decks.sh --format Standard --mechanic ganho-de-vida --colors W
./scripts/design-decks.sh --format HistoricBrawl --commander "Krenko, Mob Boss"
./scripts/design-decks.sh --format Historic --mechanic ganho-de-vida-recompensa --colors WB --include "Vito, Thorn of the Dusk Rose" --include "Revival // Revenge"
```

Como ele escolhe:

- **Motor**: sugere as mecânicas com mais cartas suas, contadas até o número de vagas do deck.
  Uma cor que já enche o deck vence duas, porque a base de mana fica melhor, e mecânicas que o
  meta usa ganham peso.
- **Cartas**: cada vaga recebe a cópia com a melhor nota. Conta a favor fazer parte do motor,
  ser jogada no meta, aparecer no meta junto com cartas já escolhidas e preencher o que ainda
  falta (criaturas, curva, remoção, compra) em comparação com os decks do meta construídos em
  volta da mesma mecânica.
- **Terrenos**: tantos quanto esses decks do meta jogam. Terrenos que geram duas cores do deck
  entram primeiro, até a metade, e os básicos seguem os símbolos de mana das mágicas.

Os decks vão para `decks/` com "(designer)" no nome, e o comando mostra os números de cada um ao
lado dos do meta. Rodar de novo substitui o arquivo do mesmo deck. A legalidade vem do
mtga-mcp, que só a tem para Standard e Historic (o Historic Brawl usa a do Historic); o Alchemy
ainda não entra.

## Segurança

- Nada aqui precisa de `sudo`. Não rode estes scripts como administrador.
- O projeto só lê arquivos locais: o banco de cartas do jogo e o banco do mtga-mcp, os dois em
  modo de leitura. Ele escreve só em `exports/`, em `decks/` e, se você instalar o agendamento,
  em `~/Library/LaunchAgents` e `~/Library/Logs/mtg-arena-collection`.
- O agendamento roda código desta pasta a cada 5 minutos com o seu usuário. Deixe a pasta num
  lugar onde só você escreve, fora de pastas compartilhadas.
- O mtga-mcp tem dependências próprias e um comando que lê a memória do jogo como administrador.
  Este projeto só roda o `mtga-mcp capture`, que lê os logs sem `sudo`.
- Achou uma falha de segurança? Conte pela aba Security do repositório, em Report a
  vulnerability, que fica privada.

## Testes

```bash
PYTHONPATH=src:tests python3 -m unittest discover -s tests
```

Só usa a biblioteca padrão do Python.

## Créditos

- [mtga-mcp](https://github.com/fkadriver/mtga-mcp): lê os logs do jogo e guarda a coleção, a
  legalidade das cartas (vinda do [Scryfall](https://scryfall.com)) e os decks do meta. Este
  projeto não inclui código dele, só chama o programa que você instalou.
- [AetherHub](https://aetherhub.com) e os outros sites de decks que o mtga-mcp importa: as listas
  do meta são deles.

## Licença

Código e documentação: [PolyForm Noncommercial 1.0.0](LICENSE.md). Você pode usar, estudar,
modificar e compartilhar para fins não comerciais, desde que toda cópia mantenha os termos da
licença e a linha de crédito:

```
Required Notice: Copyright 2026 João Vitor Lopes Capi (https://github.com/jvlcapi)
```

Uso comercial só com autorização por escrito do autor.

Nomes, textos e dados das cartas são da Wizards of the Coast e não estão cobertos por esta
licença.

## Aviso legal

mtg-arena-collection is unofficial Fan Content permitted under the
[Fan Content Policy](https://company.wizards.com/en/legal/fancontentpolicy). Not
approved/endorsed by Wizards. Portions of the materials used are property of Wizards of the
Coast. ©Wizards of the Coast LLC.

Magic: The Gathering e MTG Arena são marcas da Wizards of the Coast LLC. Os Termos de Uso da
Wizards não autorizam expressamente nenhuma ferramenta de terceiros: use por sua conta e risco.
