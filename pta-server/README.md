# Servidor PTA

Implementação em Python 3.10 ou superior, usando apenas a biblioteca padrão.

## Execução

Na raiz do repositório:

```console
python pta-server/server.py
```

O servidor escuta na porta TCP 11550. Os usuários são lidos de `users.txt`,
na mesma pasta do código, independentemente do diretório de execução.
Use Ctrl+C para encerrar.

A espera por conexões e por novos pedidos verifica o socket a cada 200 ms.
Isso permite ao Python processar Ctrl+C também no terminal do VS Code no
Windows, mesmo com um cliente conectado sem enviar dados.

## Etapa 1: conexão e apresentação

- Aceita uma conexão por vez.
- Exige `CUMP usuario` como primeiro comando.
- Valida o usuário com distinção entre maiúsculas e minúsculas.
- Responde `NOK` e fecha a conexão quando a apresentação é inválida.
- Após a apresentação, responde `NOK` a comandos desconhecidos sem fechar.
- Aceita `TERM` e responde `OK` antes de fechar.
- Repete na resposta o número recebido no pedido válido.

Exemplo de troca de mensagens, com cada pedido enviado após a resposta anterior:

```text
Cliente:  10 CUMP user1
Servidor: 10 OK
Cliente:  11 TRAP
Servidor: 11 NOK
Cliente:  12 TERM
Servidor: 12 OK
```

## Etapa 2: listagem de arquivos

Após a apresentação, `LIST` consulta a pasta `files` e responde com a quantidade
e os nomes dos arquivos, em ordem alfabética. Subdiretórios não entram na lista.
Os nomes são separados por vírgulas, sem espaços adicionais.

```text
Cliente:  11 LIST
Servidor: 11 ARQS 2 foto.png,texto.txt
```

Esse exemplo usa nomes ilustrativos. A resposta real depende do conteúdo de
`files`. Se a pasta estiver vazia, a resposta será `11 ARQS 0 `, com um espaço
após o zero. Se não for possível consultar a pasta ou representar os nomes em
ASCII, o servidor responde `NOK`. `LIST` com argumentos também recebe `NOK`,
mantendo a conexão aberta.

## Etapa 3: transferência de arquivos

`PEGA nome` envia um arquivo da pasta `files`. O servidor abre o arquivo em
modo binário e envia um cabeçalho seguido pelo conteúdo, em blocos de até
4096 bytes. O tamanho informado corresponde apenas ao conteúdo do arquivo.

```text
Cliente:  12 PEGA texto.txt
Servidor: 12 ARQ 5 hello
```

Arquivos vazios recebem o cabeçalho `ARQ 0 ` sem conteúdo depois dele.
Arquivos inexistentes, diretórios e caminhos fora de `files` recebem `NOK`.
Pedidos sem nome ou com argumentos extras também recebem `NOK`.
A conexão permanece aberta para o próximo pedido após a transferência.
Se ocorrer uma falha de leitura ou de conexão depois de iniciar o envio,
a conexão é encerrada, pois não é possível completar a resposta anunciada.

O cliente deve separar os três primeiros campos do cabeçalho e ler exatamente
a quantidade de bytes anunciada, sem converter o conteúdo para texto.
O cliente fornecido no repositório usa `decode()` no arquivo recebido e, por
isso, não é adequado para validar o PNG. Também apresenta limitações com
arquivos vazios e com a divisão das respostas entre leituras TCP.

Com o servidor atualizado rodando, execute em outro terminal, na raiz do
repositório:

```console
python pta-server/test_download.py
```

Esse teste usa `user1`, baixa todos os arquivos, compara tamanho e SHA-256
com os originais e encerra com `TERM`. Não grava cópias dos arquivos recebidos.
Ele lê as respostas em partes até completar o tamanho esperado.

## Etapa 4: validação e recepção dos pedidos

Mensagens com campos vazios, argumentos indevidos ou bytes fora de ASCII
recebem `NOK`. Quando o número do pedido ainda é legível, ele é preservado
na resposta. Para pedidos sem número de sequência legível, esta versão usa
`0 NOK`; a especificação não estabelece um número de resposta para esse caso.

TCP pode dividir um pedido entre várias leituras. O servidor reúne os trechos
até ocorrer uma pausa de 100 ms sem novos dados, configurada em `REQUEST_WAIT`.
Isso mantém compatibilidade com o cliente fornecido, que não envia nenhum
delimitador de fim de pedido. Cada cliente deve aguardar a resposta completa
antes de enviar o próximo comando.

Essa pausa é uma aproximação: se um trecho atrasar mais de 100 ms, o pedido
pode ser interpretado como incompleto. Também não há como separar com certeza
pedidos concatenados sem delimitadores. Uma solução geral exigiria definir
um marcador de fim ou um tamanho para cada pedido no protocolo. Esta versão
não altera o formato exigido pelo cliente original.

O servidor atende uma conexão por vez. Um cliente conectado que não envia
comandos mantém os demais aguardando; não há atendimento concorrente.

## Testes

Reinicie o servidor após alterar o código. Com ele rodando, execute em outro
terminal, na raiz do repositório:

```console
python pta-server/test_protocol.py
python pta-server/test_download.py
```

O primeiro comando executa 11 testes de integração: apresentação obrigatória,
usuário inválido, distinção de maiúsculas, argumentos inválidos, preservação
da sessão após erros, listagem após erro, pedidos fragmentados com intervalos
curtos, caminhos indisponíveis e desconexão sem `TERM`. O segundo verifica
tamanho e conteúdo de todos os arquivos, incluindo PNG e arquivos vazios.
Os testes usam apenas a biblioteca padrão e esperam `user1` e `user2` da
lista original. Nenhum arquivo de `files` é alterado.
