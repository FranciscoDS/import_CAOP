#!/usr/bin/python
# -*- coding: utf-8 -*-

#
# Licensed under the GNU General Public License Version 2 or later
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

# Copyright (C) 2012
#    Francisco Dos Santos <f.dos.santos@free.fr>

# dbname = PostgreSQL database parameters 
dbname = "dbname=osmosis user=caop"

# osmuser + password = OSM authentification
osmuser = "CAOPbot"
password = "*"

# comment + source = information put in changeset
comment = "Import Carta Administrativa de Portugal"
source = "IGP-CAOP-2012"

# cachesize = number max of object when building geometries
# It was intended to cache object in memory before swapping to disk but was
# never implemented due to code optimization on memory space, neverless this
# parameter is still used to allocate some static structure.
# Do not set this value too low (program will not work) or too high (memory
# hungry), a reasonable value is the number of points in the Shapefile.
cachesize = 3800000

if __name__ == '__main__':
    print "***WARNING*** THIS FILE IS NOT MEANT TO BE RUN"
    print "It is used to set some global configuration variable used by 'caop' programs."
