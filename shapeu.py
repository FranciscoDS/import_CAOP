#!/usr/bin/python

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

# Copyright (C) 2012-2013
#    Francisco Dos Santos <f.dos.santos@free.fr>

"""
Some useful stuff dealing with Point, Segment, Lines and doing
topology magic.
"""

import math
import array
import pyproj
geod = pyproj.Geod(ellps='WGS84')
precision = 9   # Compute with 9 digits but truncated for OSM to 7 digits
import logo


class ShapeUtil:
    """
    Manage unique Segment and Point
    Grouping Segments in Polyline.
    """

    def __init__(self, mem):
        self.point_pos = {}                   # (lon, lat) -> point id
        self.segment_connect = array.array('i',
                                [0] * mem)    # (point id) -> next point id
        self.coord_pnt = [None] * mem         # (point id) -> lon, lat
        self.line_seg = array.array('i',
                          [0] * (mem/2))      # (segment id) -> line id
        self.line_ends = array.array('i')     # (line id) -> segment id
        self.segment_count = 0
        self.line_count = 0
        self.cachemem = mem                   # nb object max in memory


    def makeSegment(self, lon1, lat1, lon2, lat2):
        """
        Find if point coordinates and segment have already been seen.
        Create as necessary point and/or segment, two point with same
        coordinates will only have 1 id, a line segment with the same
        ends will always get the same id.
        """

        lon1 = round(lon1, precision)
        lon2 = round(lon2, precision)
        lat1 = round(lat1, precision)
        lat2 = round(lat2, precision)
        if lon1 < lon2 or (lon1 == lon2 and lat1 < lat2):
            key1 = (lon1, lat1)
            key2 = (lon2, lat2)
        else:
            key1 = (lon2, lat2)
            key2 = (lon1, lat1)

        if (lat1==lat2 and lon1==lon2):
            # Segment with identical point happens when precision is reduced
            return None

        if self.point_pos.has_key(key1) and self.point_pos.has_key(key2):
            segmentdir1 = self.point_pos[key1]
            segmentdir2 = self.point_pos[key2]

            # Loop through all connection of both points, get the segment ids
            segmentnum = segmentdir1
            set1 = set()
            while self.segment_connect[segmentnum] != segmentdir1:
                set1.add(self.segment_connect[segmentnum] & ~1)
                segmentnum = self.segment_connect[segmentnum]
            set1.add(segmentdir1 & ~1)

            segmentnum = segmentdir2
            set2 = set()
            while self.segment_connect[segmentnum] != segmentdir2:
                set2.add(self.segment_connect[segmentnum] & ~1)
                segmentnum = self.segment_connect[segmentnum]
            set2.add(segmentdir2 & ~1)

            # There is only 1 intersection, our unique segment id
            for segmentid in set1.intersection(set2):
                return segmentid

        # Create a segment and point id (segment id + end selection)
        segmentnum = self.segment_count
        self.segment_count += 2         # Segment has 2 points
    
        if not self.point_pos.has_key(key1):
            # point id (segmentnum) has only 1 connection (himself)
            segmentdir1 = segmentnum
            self.point_pos[key1] = segmentdir1
            self.segment_connect[segmentdir1] = segmentdir1
            self.coord_pnt[segmentdir1] = key1
        else:
            # add point id to the connection linked list
            segmentdir1 = self.point_pos[key1]
            self.segment_connect[segmentnum] = self.segment_connect[segmentdir1]
            self.segment_connect[segmentdir1] = segmentnum
            self.coord_pnt[segmentnum] = key1

        if not self.point_pos.has_key(key2):
            # point id (segmentnum+1) has only 1 connection (himself)
            segmentdir2 = segmentnum+1
            self.point_pos[key2] = segmentdir2
            self.segment_connect[segmentdir2] = segmentdir2
            self.coord_pnt[segmentdir2] = key2
        else:
            # add point id to the connection linked list
            segmentdir2 = self.point_pos[key2]
            self.segment_connect[segmentnum+1] = self.segment_connect[segmentdir2]
            self.segment_connect[segmentdir2] = segmentnum + 1
            self.coord_pnt[segmentnum + 1] = key2

        return segmentnum


    def getPoint(self, lon, lat):
        """
        Find the already existing point.
        Return the id of the point or None if doesn't exist.
        """

        lon = round(lon, precision)
        lat = round(lat, precision)
        key = (lon, lat)
        if self.point_pos.has_key(key):
            return self.point_pos[key]
        return None


    def getSegment(self, pointid1, pointid2):
        """
        Find the already existing segment linking 2 points.
        Return the id of the segment or None if doesn't exist.
        """

        segmentnum = pointid1
        set1 = set()
        while self.segment_connect[segmentnum] != pointid1:
            set1.add(self.segment_connect[segmentnum] & ~1)
            segmentnum = self.segment_connect[segmentnum]
        set1.add(pointid1 & ~1)

        segmentnum = pointid2
        set2 = set()
        while self.segment_connect[segmentnum] != pointid2:
            set2.add(self.segment_connect[segmentnum] & ~1)
            segmentnum = self.segment_connect[segmentnum]
        set2.add(pointid2 & ~1)

        for segmentid in set1.intersection(set2):
            return segmentid
        return None


    def getLine(self, segmentnum):
        """
        Find the line to which belongs a segment.
        Return the id of the line or None if doesn't exist.
        """

        if self.line_seg[segmentnum/2]:
            return self.line_seg[segmentnum/2]
        return None


    def getLineEnds(self, lineid):
        """
        Find both extremity of a line.
        Return the id of the starting and ending point of the line.
        """

        idx = (lineid-1)*2
        pointid1 = self.line_ends[idx]
        pointid2 = self.line_ends[idx+1]
        pointid1 = self.point_pos[self.coord_pnt[pointid1]]
        pointid2 = self.point_pos[self.coord_pnt[pointid2]]
        return (pointid1, pointid2)


    def getLineCoords(self, lineid):
        """
        Get list of all coordinates points in a line.
        """

        idx = (lineid-1)*2
        segmentdir1 = self.line_ends[idx]
        segmentdir2 = self.line_ends[idx+1]
        coords = [ self.coord_pnt[segmentdir1] ]
        while segmentdir1^1 != segmentdir2:
            segmentdir1 = self.segment_connect[segmentdir1^1]
            coords.append(self.coord_pnt[segmentdir1])
        coords.append(self.coord_pnt[segmentdir2])
        return coords


    def iterPoints(self):
        """
        Generator function on pointid and coordinates.
        """

        for coord in self.point_pos:
            yield self.point_pos[coord], coord
        return


    def nbrPoints(self):
        """ Return number of distinct points. """
        return len(self.point_pos)


    def iterLines(self):
        """
        Generator function on lineid and list of pointid.
        """

        for lineid in xrange(self.line_count):
            segmentdir1 = self.line_ends[lineid*2]
            segmentdir2 = self.line_ends[lineid*2+1]
            pointids = [ self.point_pos[self.coord_pnt[segmentdir1]] ]
            while segmentdir1^1 != segmentdir2:
                segmentdir1 = self.segment_connect[segmentdir1^1]
                pointids.append(self.point_pos[self.coord_pnt[segmentdir1]])
            pointids.append(self.point_pos[self.coord_pnt[segmentdir2]])
            yield lineid+1, pointids
        return


    def nbrLines(self):
        """ Return number of lines. """
        return self.line_count


    def buildSimplifiedLines(self):
        """
        Grab each segment and build polylines (OSM way compatible).

        Attach a way to its successor/predecessor if there's only 1
        connection, remove useless point (simplify geometry) and make
        sure there's not too much point in a line (limit of 2000 OSM
        nodes per way).
        """

        logo.DEBUG("Before simplification %d points, %d segments" % (
                   len(self.point_pos), self.segment_count/2))
        logo.starting("Line simplification", self.segment_count)
        for segmentnum in xrange(0, self.segment_count, 2):
            logo.progress(segmentnum)
            if self.line_seg[segmentnum/2]:   # Already attached
                continue
            segmentdir1 = segmentnum
            segmentdir2 = segmentnum + 1

            # Count predecessors/successors
            nbprev = self.nbrConnection(segmentdir1)
            nbnext = self.nbrConnection(segmentdir2)
            if nbprev == 0 and nbnext == 0:
                # Orphaned segment, happens when a point is simplified
                continue

            # Affect a lineid to the current segment
            self.line_count += 1
            lineid = self.line_count
            self.line_seg[segmentdir1/2] = lineid
            coordpts = [ self.coord_pnt[segmentdir1],
                         self.coord_pnt[segmentdir2] ]

            # Join previous segments if it's the only connection
            while nbprev == 1:
                if self.line_seg[self.segment_connect[segmentdir1]/2]:
                    break               # loop on closed ring
                segmentdir1 = self.segment_connect[segmentdir1] ^ 1
                self.line_seg[segmentdir1/2] = lineid
                coordpts.insert(0, self.coord_pnt[segmentdir1])
                nbprev = self.nbrConnection(segmentdir1)

            # Join next segments if it's the only connection
            while nbnext == 1:
                if self.line_seg[self.segment_connect[segmentdir2]/2]:
                    break               # loop on closed ring
                segmentdir2 = self.segment_connect[segmentdir2] ^ 1
                self.line_seg[segmentdir2/2] = lineid
                coordpts.append(self.coord_pnt[segmentdir2])
                nbnext = self.nbrConnection(segmentdir2)

            # Find useless points
            coordpts, purgepts = simplifyPoints(coordpts)

            # Now the *not so* fun part, we change and delete some segments.
            # The ids will change so we work with point coordinates and we
            # keep track of all the dependencies.
            # A simplified point have only 2 segments, the first segment will
            # adopt a new location for its end, the second segment will be
            # entirely dereferenced.
            for coord in purgepts:
                segmentnum  = self.point_pos[coord]
                segmentdir1 = self.segment_connect[segmentnum]
                segmentdir2 = segmentdir1^1
                self.segment_connect[segmentnum] = self.segment_connect[segmentdir2]
                seg = self.segment_connect[segmentdir2]
                while self.segment_connect[seg] != segmentdir2:
                    seg = self.segment_connect[seg]
                self.segment_connect[seg] = segmentnum
                self.segment_connect[segmentdir1] = segmentdir1
                self.segment_connect[segmentdir2] = segmentdir2

                # Update new end point location
                coord2 = self.coord_pnt[segmentdir2]
                self.coord_pnt[segmentnum] = coord2
                if self.point_pos[coord2] == segmentdir2:
                    self.point_pos[coord2] = segmentnum
                del self.point_pos[coord]
                self.coord_pnt[segmentdir1] = None
                self.coord_pnt[segmentdir2] = None
                self.line_seg[segmentdir2/2] = 0


            # Split if we are too close to the limit of 2000 nodes
            # and ensure that a new line have more than a few points
            # we also record both extremity of a line for later use
            segmentdir1 = self.point_pos[coordpts[0]]
            segmentdir2 = self.point_pos[coordpts[1]]
            segmentnum = self.getSegment(segmentdir1, segmentdir2)
            if self.coord_pnt[segmentnum] != coordpts[0]:
                segmentnum = segmentnum^1
            self.line_ends.append(segmentnum)
            while len(coordpts) > 1980:
                # End of previous line and start a new one
                self.line_count += 1
                lineid = self.line_count
                segmentdir1 = self.point_pos[coordpts[1949]]
                coordpts = coordpts[1950:]
                segmentdir2 = self.point_pos[coordpts[0]]
                segmentnum = self.getSegment(segmentdir1, segmentdir2)
                if self.coord_pnt[segmentnum] != coordpts[0]:
                    segmentnum = segmentnum^1
                self.line_ends.append(segmentnum)
                segmentnum = self.segment_connect[segmentnum]
                self.line_ends.append(segmentnum)
                for i in xrange(1, min(1980, len(coordpts))):
                    self.line_seg[segmentnum/2] = lineid
                    segmentnum = self.segment_connect[segmentnum^1]
            segmentdir1 = self.point_pos[coordpts[-2]]
            segmentdir2 = self.point_pos[coordpts[-1]]
            segmentnum = self.getSegment(segmentdir1, segmentdir2)
            if self.coord_pnt[segmentnum] != coordpts[-1]:
                segmentnum = segmentnum^1
            self.line_ends.append(segmentnum)
        logo.ending()
        logo.DEBUG("After simplification %d points, %d lines" % (
                   len(self.point_pos), self.line_count))


    def nbrConnection(self, pointid):
        """ Return number of connection for a given point id. """

        cnt = 0
        segmentnum = pointid
        while self.segment_connect[segmentnum] != pointid:
            cnt += 1
            segmentnum= self.segment_connect[segmentnum]
        return cnt


def simplifyPoints(points):
    """
    Simplify a line (ordered list of points).
    Looks like a Douglas-Peucker but without recursion (quicker as we not
    seek the optimal simplification) and preserving the big angles.
    """

    # The first and last point are never simplified (for a line)
    # but for a ring this means that one point which could possibly be
    # simplified will never be tried
    resultpnt = [ points[0] ]
    deletepnt = []
    lon1, lat1 = points[0]
    lon2, lat2 = points[1]
    angle1, dist1 = angledistance(lon1, lat1, lon2, lat2)
    cache = [ (angle1, dist1) ]   # store previous result (angle, distance)

    for pnt in xrange(1, len(points)-1):
        # Compute all angle and distance needed to judge usefulness for
        # the '-nth points in one step (thanks to pyproj and lists)
        lon2, lat2 = points[pnt]
        lon3, lat3 = points[pnt+1]
        tlonsrc = [ lon1, lon2 ]
        tlatsrc = [ lat1, lat2 ]
        tlondst = [ lon3 ] * (len(cache)+1)
        tlatdst = [ lat3 ] * (len(cache)+1)
        for j in xrange(1, len(cache)):
            lon2, lat2 = points[pnt-j]
            tlonsrc.append(lon2)
            tlatsrc.append(lat2)
        angles, dists = angledistance(tlonsrc, tlatsrc, tlondst, tlatdst)

        # Verify constraint (angle and deviation) for current point and
        # previously simplified points
        dist3 = dists[0]
        for j in xrange(len(cache)):
            angle1, dist1 = cache[j]
            angle2 = angles[j+1]
            dist2 = dists[j+1]
            diffangle = angle2 - angle1
            if diffangle < -180:
                diffangle += 360
            elif diffangle > 180:
                diffangle -= 360
            deviation = getdeviation(diffangle, dist1, dist2, dist3)

            if (abs(diffangle) >= 45.0 - abs(deviation)*18.0
              or abs(deviation) >= 2.0):
                # cannot simplify pnt as it will break constraint
                cache = [ (angles[1], dists[1]) ]
                resultpnt.append(points[pnt])
                lon1, lat1 = points[pnt]
                break

        else:
            # constraint verified for all points, we can simplify pnt
            cache.insert(0, (angles[0], dists[0]) )
            deletepnt.append(points[pnt])

    resultpnt.append(points[-1])
    return (resultpnt, deletepnt)


def angledistance(lonsrc, latsrc, londst, latdst):
    """
    Compute angle and distance from (lonsrc, latsrc) to (londst, latdst).
    The parameters can also be arrays (quicker to do 1 call to pyproj with
    N calculation than N call with 1 calculation).
    """

    try:
        angles, dummy, dists = geod.inv(lonsrc, latsrc, londst, latdst)
    except:
        # oups, got an exception with valid coordinates
        # (see http://code.google.com/p/pyproj/issues/detail?id=18)
        # with WGS84 if coordinates are too close, proj4 gives us a NaN
        # until http://trac.osgeo.org/proj/ticket/129 is fixed,
        # fallback to haversine formulae (only for the troublesome coordinates)
        if type(lonsrc) is float or len(lonsrc)==1:
            if type(lonsrc) is float:
                x1 = lonsrc
                y1 = latsrc
                x2 = londst
                y2 = latdst
            else:
                x1 = lonsrc[0]
                y1 = latsrc[0]
                x2 = londst[0]
                y2 = latdst[0]
            dx = x2 - x1
            dy = y2 - y1
            angle = math.acos( dy/math.sqrt(dx*dx + dy*dy) ) / math.pi * 180
            angle = math.copysign(angle, dx)
            rlat1 = math.radians(y1)
            rlon1 = math.radians(x1)
            rlat2 = math.radians(y2)
            rlon2 = math.radians(x2)
            p = math.sin((rlat2-rlat1)/2)**2 + math.cos(rlat1) * math.cos(rlat2) * math.sin((rlon2-rlon1)/2)**2
            q = 2 * math.atan2(math.sqrt(p), math.sqrt(1-p))
            dist = 6371000*q
            if type(lonsrc) is float:
                return (angle, dist)
            else:
                return ([angle], [dist])
        else:
            middle = len(lonsrc)/2
            angles, dists = angledistance(lonsrc[:middle], latsrc[:middle],
                                          londst[:middle], latdst[:middle])
            angle2, dist2 = angledistance(lonsrc[middle:], latsrc[middle:],
                                          londst[middle:], latdst[middle:])
            angles.extend(angle2)
            dists.extend(dist2)

    return (angles, dists)


def getdeviation(diffangle, dist1, dist2, dist3):
    # diffangle = 180 - realangle
    angle = math.radians(diffangle)
    return (dist1 * dist2 * math.sin(angle) / dist3)
