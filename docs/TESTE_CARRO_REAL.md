# Teste em carro real: o que fazer em cada carro

O Torqis passa nos testes com os simuladores, mas só um carro real prova que funciona. Esta folha diz o que fazer
em cada carro para que cada ida à oficina deixe provas que se possam usar. Uma gravação de um carro real passa a
ser um teste automático (`tests/captures/`), e o programa nunca mais pode deixar de funcionar nesse carro sem que
os testes falhem.

**Regra de ouro:** nos primeiros carros, **só leitura**. Nada de apagar avarias, codificar ou adaptar até as leituras
estarem confirmadas em vários carros.

## Antes de sair

- [ ] Portátil carregado, com o carregador.
- [ ] O cabo (KKL 409.1 com chip FTDI; OBDLink EX para os CAN) e o cabo USB de reserva, se houver.
- [ ] **Em casa, com o cabo ligado ao PC:** Opções → Detectar cabo. Tem de aparecer "Cabo FTDI pronto". Se
      disser que falta um ajuste, carregue em **Ajustar cabo** (o Windows pede autorização), desligue e volte a
      ligar o cabo e detecte outra vez. Os cabos HEX (VCDS) não servem: o Torqis não lê controladores por eles.
- [ ] Torqis instalado a partir do **instalador da última versão** (não da pasta de desenvolvimento).
- [ ] Atalho para o modo técnico: copiar o atalho do Torqis e acrescentar ` --tecnico` ao destino. Este modo mostra
      a **Validação no carro**, o protocolo e o registo da comunicação.
- [ ] Um bloco de notas ou o telemóvel para fotografar o painel e o autocolante do VIN.

## Carros a procurar (por ordem de prioridade)

| # | Carro | Porquê | Cabo |
|---|-------|--------|------|
| 1 | VW/Audi/Seat/Skoda TDI de 1998 a 2004 (Golf IV, A3 8L, Leon 1M, Octavia 1U) | Linha K, KW1281: o caso mais comum dos clientes | KKL FTDI |
| 2 | Um carro de 2004 a 2008 com KWP2000 na linha K (Golf V inicial, Passat B6 inicial) | Byte de estado das avarias e sessões KWP | KKL FTDI |
| 3 | Golf VI / Passat B6-B7 / A3 8P (CAN, TP2.0) | Protocolo CAN da VAG | OBDLink EX ou J2534 |
| 4 | Um VAG de 2013 em diante (Golf VII, MQB) | Só OBD genérico do motor (o Auto-Scan VAG por UDS ainda não existe) | OBDLink EX |
| 5 | Qualquer carro de outra marca a gasolina, de 2001 em diante | OBD-II genérico com ELM327 | ELM327 |
| 6 | Um ELM327 clone barato (de 5 a 10 €) | Os clones respondem de forma diferente | ELM327 clone |

## Em cada carro (cerca de 15 minutos)

1. **Ignição ligada, motor desligado.** Ligar o cabo ao carro e só depois ao PC.
2. **Opções → Testar ligação.** Anotar o resultado (eco da linha K, versão do ELM, etc.).
3. **Opções → Gravar comunicação → começar.** A gravação fica a correr durante todo o teste.
4. **Auto-Scan.** Deixar acabar. Fotografar o ecrã com a lista dos módulos.
5. **Comparar com o painel e com outra ferramenta**, se houver (VCDS, Delphi, etc.):
   - [ ] Os módulos encontrados são os do carro?
   - [ ] As avarias são as mesmas e têm a mesma descrição?
   - [ ] O estado (permanente/intermitente) bate certo?
6. **Abrir o 01 Motor:**
   - [ ] Informação: a referência da peça e a codificação estão certas?
   - [ ] Medição: abrir o grupo 001 durante 30 s. A rotação e a temperatura batem certo com o painel?
   - [ ] Pôr o motor a trabalhar e repetir a medição. A rotação acompanha o pedal?
7. **No modo técnico: Opções → Validação no carro → Iniciar.** Não marcar "No fim, apagar as avarias do motor" nos primeiros carros.
   No fim, guardar o relatório.
8. **OBD (se for outra marca ou se houver ELM327):** OBD → Ligar ao veículo → ler avarias e valores ao vivo.
9. **Parar a gravação** (Opções → Gravar comunicação → parar).
10. **Relatório para o cliente → Guardar PDF.** Ver se está legível e se não falta nada.

## Se alguma coisa falhar

Não desligues nada. Faz pela ordem:

1. **Fotografa o ecrã** com a mensagem de erro.
2. **Para a gravação** (Opções → Gravar comunicação).
3. **Opções → Pacote de suporte.** Junta o registo, as definições e a gravação num `.zip`.
4. Anota: o carro, o ano, o motor, o cabo, o que estavas a fazer e se o carro estava com o motor a trabalhar.

## Depois de cada carro

Guardar numa pasta com o nome do carro (por exemplo `golf4_asz_2002_kkl`):

- [ ] a gravação `.radrec`
- [ ] o relatório da Validação no carro (`.html`)
- [ ] o pacote de suporte, se houve erros
- [ ] as fotografias (Auto-Scan, painel, outra ferramenta)
- [ ] uma linha de notas: o que bateu certo, o que não bateu

Com isto, cada gravação passa a teste automático em `tests/captures/`, com um nome do tipo
`golf4_asz_kkl_01_17_03.radrec`. Cada erro vira uma correção com um teste que garante que não volta.

## Quando se pode dizer "testado em carro real"

- [ ] Pelo menos 3 carros diferentes da linha 1 e 1 de cada uma das linhas 2 a 5, sem erros na leitura.
- [ ] Avarias e valores iguais aos de outra ferramenta em todos.
- [ ] Só depois disso: apagar avarias num carro com avarias antigas (não críticas) e confirmar que o
      Torqis volta a ler a memória vazia.
- [ ] Codificação e adaptação: só num carro teu ou de confiança, sempre com a codificação original anotada (o
      Torqis guarda-a no separador Alterações).
