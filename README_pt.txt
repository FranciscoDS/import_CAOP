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
  - osmosis --read-xml file=portugal-latest.osm.bz2 \
            --write-pgsimp database=osmosis user=caop


O ficheiro portugal-latest.osm.bz2 que deve ser recuperado do site de geofabrik
(http://download.geofabrik.de/europe/portugal.html) ficará assim integrado na
base de dados.
Se usaram o ficheiro portugal-latest.osm.pbf modifica o comando osmosis e
usam --read-pbf em vez do --read-xml.
 
Nota: os Açores não estão incluído no ficheiro de Portugal e são disponível
no geofabrik em http://download.geofabrik.de/europe/azores.html.

Os dados CAOP são importados no schema osmosis em tabelas diferentes dos dados
OSM, por isso a base de dados pode ser constituído na ordem e as vezes que
quiseram.


Configuração :
--------------

O ficheiro 'caop_config.py' permite alterar a configuração do programa.
O mais importante é o 'dbname' que permite identificar a base de dados.
É aconselhado ativar o ficheiro de log em 'logfile' e eventualmente aumentar
o nível de debug em 'verbose'.

Uma vez que foi configurado basta chamar os programas por ordem :
  - caop_build.py para convertir a CAOP em objetos compatível OSM
  - caop_diff.py para comparar e detectar as mudança com os objetos OSM


Conversão
---------

A importação dos dados CAOP na base de dados local é feito pelo programa
caop_build.py e é preciso lhe dar o nome do ficheiro ou dos ficheiros
Shapefile par ser convertidos :

  - python caop_build.py ArqAcores_GCentral_AAd_CAOP2011.shp \
                         ArqAcores_GOcidental_AAd_CAOP2011.shp \
                         ArqAcores_GOriental_AAd_CAOP2011.shp


Os dados serão acrescentados na base de dados, isto significa que pode-se
usar o programa de 2 maneiras :

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


Comparação
----------

O programa caop_diff.py faz a comparação com os dados já existente.
É necessário fazer a integração dos dados OSM indicado na preparação antes
de user este programa.

  - python caop_diff.py


Por enquanto o programa só identifica as relações já existente.
