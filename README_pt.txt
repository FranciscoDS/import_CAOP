Introdução :
------------

O programa caop_build é um programa livre com licença GPL.
Este programa foi desenvolvido e testado com as seguintes versões de software :

  - Python 2.7.3
  - gdal 1.7.3
  - postgresql 9.1.3
  - postgis 1.5.3
  - psycopg2 2.4.5
  - osmosis 0.40.1


Outras versões mais recentes ou mais velhas também devem dar, a exceção da
versão de Python que deve ser uma 2.6 ou 2.7, não deve haver nenhum problema
em encontrar esses softwares em package já disponibilizado com qualquer
distribuição Linux.

Não esquecer instalar os packages com os bindings Python. Se um package não
está presente na sua distribuiçao Linux é preciso fazer a instalação a partir
do código fonte, não esquecer instalar os packages 'dev' por este efeito.



Preparação :
------------

Uma vez que PostgreSQL está instalado, criar uma base de dados OSM com o schema
osmosis :

  - createdb osmosis
  - createuser caop
  - psql -d osmosis -f /usr/share/pgsql/contrib/postgis-64.sql
  - psql -d osmosis -f /usr/share/pgsql/contrib/spatial_ref_sys.sql
  - psql -d osmosis
    - ALTER TABLE geometry_columns OWNER TO caop;
    - ALTER TABLE spatial_ref_sys OWNER TO caop;
  - psql -d osmosis -f pgsimple_schema_0.6.sql
  - osmosis --read-xml file=portugal.osm.bz2 \
            --write-pgsimp database=osmosis user=caop


O ficheiro portugal.osm.bz2 que deve ser recuperado do site de geofabrik
(http://download.geofabrik.de/osm/) ficará assim integrado na base de dados.
Esta parte não é obrigatório, o programa que permite a comparação dos dados
CAOP com os dados já existente no OSM ainda não foi desenvolvido.
O 'caop_build.py' trabalha no schema osmosis com tabelas diferentes do OSM.



Execução :
----------

O ficheiro 'caop_config.py' permite alterar a configuração do programa.
O mais importante é o 'dbname' que permite identificar a base de dados.
Uma vez que foi configurado basta chamar o programa com o ficheiro ou os
ficheiros Shapefile para ser convertidos :

  - python caop_build.py ArqAcores_GCentral_AAd_CAOP2011.shp \
                         ArqAcores_GOcidental_AAd_CAOP2011.shp \
                         ArqAcores_GOriental_AAd_CAOP2011.shp


Os dados convertidos em formato OSM vão ser integrados na base de dados (isto
demora um bocadinho, deixar o programa trabalhar sozinho). Os dados serão
acrescentados, isto significa que pode-se usar o programa de 2 maneiras :

  - execução duma só vez com todos os Shapefile a converter (se tiverem
    memoria suficiente).
  - 3 execuçao separadas, uma para o continente, outra para os Açores e
    outra para a Madeira.


Toma nota que os 3 ficheiros dos Açores TEM QUE SER convertidos ao mesmo tempo.

Se quiseram apagar o conteúdo da base de dados para ter uma execução limpa
(iniciado com uma base de dados vazia), basta remover um dos elementos
importantes, por exemplo, o atribuidor de identificação única aos objetos :

  - psql -d osmosis
    - DROP SEQUENCE seq_caop_id;


Para que possam ver o resultado, o pequeno programa 'testsql.py' permite criar
um ficheiro .osm :

  - python testsql.py ficheiro.osm

Que pode ser aberto usando um dos editor OSM (JOSM ou Merkaartor) se a memoria
do seu computador o permite.

Este ficheiro não pode e não deve ser enviado para OSM, é demasiado grande e
falta a comparação com os dados já existente.



Falta para fazer :
------------------

Falta o programa que permite identificar e misturar os dados OSM com os dados
CAOP.
Também falta o programa que permite o envio em grande escala para OSM (inicio).

