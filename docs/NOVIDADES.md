# Novidades

O que muda em cada versão, escrito para os clientes. O programa mostra estas linhas antes de actualizar, no idioma
da interface (`### pt` e `### en`). Linguagem simples, sem nomes técnicos (cabos, protocolos, ficheiros).

Ao publicar uma versão, `tools/finish_build.py notes <versão>` junta a secção dessa versão ao texto da Release.
Uma versão sem secção aqui é publicada sem novidades (o programa só diz que há uma versão nova).

## 1.25.1

### pt
- Correcções: o Ajustar cabo só diz que ficou feito quando o cabo ficou mesmo ajustado (e a janela já não congela),
  o aviso da licença abre o separador Licença, e no Histórico as visitas sem matrícula já não aparecem juntas.

### en
- Fixes: Adjust cable only reports success when the cable really was adjusted (and the window no longer freezes),
  the licence notice opens the Licence tab, and in History visits without a plate are no longer lumped together.

## 1.25.0

### pt
- Opções, Histórico, Controladores e OBD redesenhados: as Opções estão em separadores (Cabo, Oficina, Licença,
  Programa), o Histórico mostra cada carro com as suas visitas e os Controladores têm um só campo para o endereço ou
  o nome.
- Novo botão **Ajustar cabo** no Detectar cabo: deixa o cabo VAG a ler mais depressa (o Windows pede autorização
  uma vez).

### en
- Options, History, Control modules and OBD redesigned: Options has tabs (Cable, Workshop, Licence, Program),
  History shows each car with its visits, and Control modules has a single field for the address or the name.
- New **Adjust cable** button in Detect cable: makes the VAG cable read faster (Windows asks for permission once).

## 1.24.0

### pt
- Ecrãs mais simples e directos: o Início é o carro na oficina e o botão do Auto-Scan (clique num carro recente
  para o voltar a abrir), o controlador abre logo nas avarias e o Auto-Scan mostra só as avarias, por controlador.

### en
- Simpler, more direct screens: Home is the car in the workshop and the Auto-Scan button (click a recent car to
  open it again), a module opens straight on its faults, and the Auto-Scan shows only the faults, by module.

## 1.23.2

### pt
- A página de transferências do Torqis tem um nome novo. O programa continua a actualizar-se sozinho.

### en
- The Torqis download page has a new name. The program keeps updating itself.

## 1.23.1

### pt
- As actualizações e as transferências passam a vir de uma página própria do Torqis. Não é preciso fazer nada: o
  programa continua a actualizar-se sozinho.

### en
- Updates and downloads now come from a page of Torqis's own. Nothing to do: the program keeps updating itself.

## 1.23.0

### pt
- Nos primeiros 14 dias está tudo desbloqueado. Depois, sem licença, o programa continua a ligar ao carro e a
  dizer que módulos têm avarias, mas mostra só parte das avarias e dos valores. Com licença não muda nada.

### en
- For the first 14 days everything is unlocked. After that, without a licence, the program still connects to the
  car and says which modules have faults, but shows only part of the faults and values. With a licence nothing
  changes.

## 1.22.0

### pt
- O programa passa a chamar-se Torqis, com nome, logótipo e cores novos. O histórico, os clientes, a licença, o
  logótipo da oficina e as definições passam sozinhos para a versão nova — não é preciso fazer nada.

### en
- The program is now called Torqis, with a new name, logo and colours. History, customers, licence, workshop logo
  and settings move over to the new version by themselves — nothing to do.

## 1.21.0

### pt
- O simulador parece-se mais com um carro real: responde um Golf IV completo (caixa, ar condicionado, airbags,
  conforto e rádio, além de motor, ABS e painel), as avarias presentes voltam depois de apagar, o que se apaga ou
  codifica fica guardado, e o motor arranca frio e aquece.
- Em Opções pode escolher o carro do simulador: Golf IV, Golf IV sem avarias, Golf V, e carros a gasolina de
  outras marcas com OBD por linha K, KWP2000 e J1850. Também pode simular um adaptador OBD barato.

### en
- The simulator is closer to a real car: a whole Golf IV answers (gearbox, air conditioning, airbags, comfort and
  radio, besides engine, ABS and instruments), present faults come back after clearing, what you clear or code
  stays stored, and the engine starts cold and warms up.
- In Options you can choose the simulator car: Golf IV, Golf IV without faults, Golf V, and petrol cars of other
  makes with OBD over the K-line, KWP2000 and J1850. You can also simulate a cheap OBD adapter.

## 1.20.3

### pt
- Nas avarias de um controlador, o estado (Intermitente/Permanente) deixou de poder sair com a mesma cor que a
  gravidade (alta/média/baixa) — já não se confundem na tabela.

### en
- In a module's faults, the state (Intermittent/Permanent) no longer shares a colour with the severity
  (high/medium/low) — the two no longer look the same in the table.

## 1.20.2

### pt
- No relatório para o cliente, a cor da saúde do veículo passa a condizer sempre com o texto (vermelho quando é
  recomendada uma intervenção).

### en
- In the customer report, the colour of the vehicle health always matches its text (red when an intervention is
  recommended).

## 1.20.1

### pt
- Auto-Scan: depois de apagar as avarias em todos os controladores, o assistente de diagnóstico já não fica a
  mostrar uma avaria que foi apagada.

### en
- Auto-Scan: after clearing the faults in all modules, the diagnostic assistant no longer keeps showing a fault
  that was cleared.

## 1.20.0

### pt
- Lista de controladores arrumada por sistema do carro; depois de um Auto-Scan, os que responderam aparecem no topo
  ("Neste carro") com o resultado a cores.
- Relatório para o cliente com um aspecto mais profissional: a saúde do veículo em destaque e os dados do carro
  mais arrumados.
- Auto-Scan com mais espaço para a lista de avarias e para o assistente de diagnóstico.
- Letra um pouco maior em todo o programa, para se ler melhor a partir do carro.

### en
- Module list arranged by car system; after an Auto-Scan, the ones that answered are at the top ("In this car")
  with the result in colour.
- More professional customer report: the vehicle health stands out and the car details are tidier.
- Auto-Scan with more room for the fault list and the diagnostic assistant.
- Slightly larger text throughout the program, to read better from inside the car.

## 1.19.0

### pt
- Ao abrir um controlador, a página Informação mostra o que pode fazer nele, com um atalho para cada função.
- Testes TDI mais claros: cada teste num cartão, com o primeiro já escolhido.
- Opções e tabelas mais arrumadas e fáceis de ler.

### en
- When you open a module, the Information page shows what you can do in it, with a shortcut to each function.
- Clearer TDI tests: each test on a card, with the first one already selected.
- Tidier, easier to read Options and tables.

## 1.18.0

### pt
- Novo logótipo: o "R" de Roots com o ponteiro de um conta-rotações na zona vermelha. Lê-se bem mesmo em
  pequeno, na barra de tarefas.

### en
- New logo: the "R" of Roots with the needle of a rev counter in the red zone. It reads well even when small, on
  the taskbar.

## 1.17.0

### pt
- Nova página Início, mais simples: o estado do cabo e do carro logo no topo, com o botão para começar o
  Auto-Scan.
- A matrícula do carro em diagnóstico aparece em destaque, e os últimos veículos mostram logo, a cores, se tinham
  avarias.

### en
- New, simpler Home page: the cable and car status right at the top, with the button to start the Auto-Scan.
- The number plate of the car being diagnosed stands out, and the latest vehicles show at a glance, in colour,
  whether they had faults.

## 1.16.2

### pt
- Os valores com casas decimais aparecem com vírgula (por exemplo 12,4 V), como é habitual em Portugal.
- Mostradores mais limpos: os números da escala já não ficam por cima do valor.
- Caixas de números com setas visíveis e mais fáceis de ler.
- Na lista de avarias, o assistente de diagnóstico tem mais espaço e lê-se melhor.

### en
- Clearer gauges: the scale numbers no longer overlap the value.
- Number boxes with visible arrows and easier to read.
- In the fault list, the diagnostic assistant has more room and is easier to read.

## 1.16.1

### pt
- Ligação mais estável durante a leitura de valores, mesmo com o computador ocupado a desenhar os gráficos.
- O computador já não entra em suspensão a meio de uma ligação ao carro (por exemplo, num portátil a bateria
  durante um Auto-Scan).
- Se o programa fechar sozinho, fica um registo que permite perceber porquê.

### en
- More stable connection while reading measuring values, even when the computer is busy drawing the charts.
- The computer no longer goes to sleep in the middle of a connection to the car (for example, a laptop on battery
  during an Auto-Scan).
- If the program closes by itself, a log is left that makes it possible to find out why.

## 1.16.0

### pt
- Ligação mais estável aos controladores mais antigos: o programa dá-lhes o tempo de que precisam entre cada
  pedido, e a comunicação deixa de cair a meio.
- Se um controlador responder mas a ligação não arrancar à primeira, o programa espera um momento e tenta outra vez
  sozinho — também no Auto-Scan.
- Arranque da ligação mais seguro depois de um erro ou de mexer no cabo.
- Voltar a abrir um controlador é mais rápido: o programa lembra-se de como falou com ele da última vez.

### en
- More stable connection to older controllers: the program gives them the time they need between requests, and the
  communication no longer drops halfway.
- If a controller answers but the connection does not start the first time, the program waits a moment and tries
  again by itself — in Auto-Scan too.
- Safer start of the connection after an error or after the cable has been moved.
- Opening a controller again is faster: the program remembers how it talked to it the last time.

## 1.15.1

### pt
- Mensagens sobre o cabo mais simples e claras.

### en
- Simpler, clearer messages about the cable.

## 1.15.0

### pt
- Ligação mais rápida e mais segura aos controladores antigos que comunicam a outras velocidades (painéis, airbags,
  alguns ABS e rádios): o programa percebe logo à primeira tentativa qual é a velocidade certa.
- Se a ligação a um controlador falhar logo a seguir ao arranque, o programa tenta sozinho outra vez antes de
  desistir.

### en
- Faster and more reliable connection to older controllers that talk at other speeds (instrument clusters, airbags,
  some ABS units and radios): the program works out the right speed from the first attempt.
- If the connection to a controller fails right after it starts, the program tries again by itself before giving
  up.

## 1.14.2

### pt
- Novo "Ver gravações": veja os valores gravados em gráfico, com mínimo, máximo e média, e compare duas gravações
  (por exemplo, antes e depois de uma reparação).
- Enquanto lê os valores do motor, o programa avisa logo quando algo sai do normal: pressão do turbo, massa de ar,
  injectores, temperatura do motor ou tensão da bateria.
- As gravações ficam guardadas com o carro: na visita seguinte o programa compara sozinho com a anterior.
- O relatório passa a mostrar os valores lidos e os avisos que apareceram; o relatório técnico compara com a
  visita anterior.
- A actualização automática da versão portátil passa a esperar sempre que o programa feche antes de trocar os
  ficheiros.

### en
- New "View recordings": see the recorded values on a chart, with minimum, maximum and average, and compare two
  recordings (for example, before and after a repair).
- While reading the engine values, the program warns you straight away when something is out of the ordinary: boost
  pressure, air mass, injectors, engine temperature or battery voltage.
- Recordings are kept with the car: on the next visit the program compares with the previous one by itself.
- The report now shows the values read and the warnings that appeared; the technical report compares with the
  previous visit.
- The automatic update of the portable version now always waits for the program to close before replacing the
  files.

## 1.14.1

### pt
- Novo "Ver gravações": veja os valores gravados em gráfico, com mínimo, máximo e média, e compare duas gravações
  (por exemplo, antes e depois de uma reparação).
- Enquanto lê os valores do motor, o programa avisa logo quando algo sai do normal: pressão do turbo, massa de ar,
  injectores, temperatura do motor ou tensão da bateria.
- As gravações ficam guardadas com o carro: na visita seguinte o programa compara sozinho com a anterior.
- O relatório passa a mostrar os valores lidos e os avisos que apareceram; o relatório técnico compara com a
  visita anterior.

### en
- New "View recordings": see the recorded values on a chart, with minimum, maximum and average, and compare two
  recordings (for example, before and after a repair).
- While reading the engine values, the program warns you straight away when something is out of the ordinary: boost
  pressure, air mass, injectors, engine temperature or battery voltage.
- Recordings are kept with the car: on the next visit the program compares with the previous one by itself.
- The report now shows the values read and the warnings that appeared; the technical report compares with the
  previous visit.

## 1.14.0

### pt
- Novo "Ver gravações": veja os valores gravados em gráfico, com mínimo, máximo e média, e compare duas gravações
  (por exemplo, antes e depois de uma reparação).
- Enquanto lê os valores do motor, o programa avisa logo quando algo sai do normal: pressão do turbo, massa de ar,
  injectores, temperatura do motor ou tensão da bateria.
- As gravações ficam guardadas com o carro: na visita seguinte o programa compara sozinho com a anterior.
- O relatório passa a mostrar os valores lidos e os avisos que apareceram; o relatório técnico compara com a
  visita anterior.

### en
- New "View recordings": see the recorded values on a chart, with minimum, maximum and average, and compare two
  recordings (for example, before and after a repair).
- While reading the engine values, the program warns you straight away when something is out of the ordinary: boost
  pressure, air mass, injectors, engine temperature or battery voltage.
- Recordings are kept with the car: on the next visit the program compares with the previous one by itself.
- The report now shows the values read and the warnings that appeared; the technical report compares with the
  previous visit.

## 1.13.0

### pt
- O programa actualiza-se sempre sozinho, também na versão portátil: não precisa de fazer nada.
- Antes de actualizar, o programa mostra o que há de novo.
- Se uma actualização não terminar, o programa continua a funcionar na versão anterior e avisa.
- Se uma versão nova não abrir no seu computador, o programa volta sozinho à versão anterior.
- O pacote de suporte tira os números de chassis e as matrículas dos registos e leva mais informação para
  resolver problemas mais depressa.

### en
- The program always updates itself, also in the portable version: there is nothing to do.
- Before updating, the program shows what is new.
- If an update does not finish, the program keeps working on the previous version and tells you.
- If a new version does not open on your computer, the program goes back to the previous version by itself.
- The support package removes chassis numbers and number plates from the logs and includes more information to
  solve problems faster.

## 1.12.1

### pt
- As actualizações passam a instalar-se sozinhas.
- Novo botão "Actualizar agora": instala a versão nova e volta a abrir o programa.

### en
- Updates now install by themselves.
- New "Update now" button: installs the new version and opens the program again.
