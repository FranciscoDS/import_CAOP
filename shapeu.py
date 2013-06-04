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
            coordpts, purgepts = simplifyShapeZV(coordpts, purgepts)
            coordpts, purgepts = fixSelfIntersect(coordpts, purgepts)

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


    def isRingValid(self, points):
        """
        Check if ring (ordered list of points) is well formed.
        Return False if self-intersecting or self-touching.
        """

        assert points[0] == points[-1], (
                   "Ring not closed %r <-> %r" % (points[0], points[-1]) )

        # LinearRing should be simple
        # - point (except first/last) appearing once
        # - no intersecting line
        if len(set(points)) < len(points)-1:
            return False
        if findLineIntersection(points):
            return False
        return True


def simplifyPoints(points):
    """
    Simplify a line (ordered list of points).
    Use a Douglas-Peucker with a small distance and preserve big angles.
    """

    # The first and last point are never simplified (for a line)
    # but for a ring this means that one point which could possibly be
    # simplified will never be tried
    resultpnt = [ points[0] ]
    deletepnt = []
    pnt1 = 0
    stack = [ len(points)-1 ]
    while len(stack) > 0:
        # Compute angle and distance to find the most significant point
        # between pnt1 and pnt2
        pnt2 = stack[-1]
        angle_0, dist_0 = angledistance(points[pnt1][0], points[pnt1][1],
                                        points[pnt2][0], points[pnt2][1])
        pntfound = None
        devfound = 0
        for pt in xrange(pnt1+1, pnt2):
            angle_1, dist_1 = angledistance(points[pnt1][0], points[pnt1][1],
                                            points[pt][0], points[pt][1])
            angle_2, dist_2 = angledistance(points[pt][0], points[pt][1],
                                            points[pnt2][0], points[pnt2][1])
            deviation = getdeviation(diffheading(angle_0, angle_1),
                                     dist_0, dist_1, dist_2)
            if deviation > devfound:
                if deviation >= 2.0:
                    pntfound = pt
                    devfound = deviation
                elif deviation >= 0.3:
                    diffangle = diffheading(angle_2, angle_1)
                    if abs(diffangle) >= 40.0 - abs(deviation)*16.0:
                        pntfound = pt
                        devfound = deviation

        if pntfound is None:
            deletepnt.extend([ points[i] for i in xrange(pnt1+1,pnt2) ])
            pnt1 = stack.pop()
            resultpnt.append(points[pnt1])
        else:
            stack.append(pntfound)

    return (resultpnt, deletepnt)


def simplifyShapeZV(points, ptsdeleted):
    """
    Simplify some very big angles in line.
    Remove 1 point if shapes looking like a Z or V.
    """

    angledist = [ angledistance(points[i-1][0],
                                points[i-1][1],
                                points[i][0],
                                points[i][1])
                     for i in xrange(1, len(points)) ]

    ptsdiscard = []
    i = 0
    while i < len(angledist)-1:
        # Search very big angles
        diffangle = diffheading(angledist[i][0], angledist[i+1][0])
        if abs(diffangle) <= 90.0:
            i += 1
            continue

        #
        # Two big angles in a row = Z shape
        # 0---1
        #    /
        #   2---3
        #
        if abs(diffangle) > 135.0 and i < len(angledist)-2 and abs(
           diffheading(angledist[i+1][0], angledist[i+2][0])) > 135.0:
            angle_1, dist_1 = angledist[i]
            angle_2, dist_2 = angledist[i+1]
            angle_3, dist_3 = angledist[i+2]
            angle_A, dist_A = angledistance(points[i+1][0], points[i+1][1],
                                            points[i+3][0], points[i+3][1])
            # Distance of point 1 to line 2-3
            d1 = getdeviation(diffheading(angle_3, angle_A),
                              dist_3, dist_A, dist_2)
            angle_B, dist_B = angledistance(points[i][0], points[i][1],
                                            points[i+2][0], points[i+2][1])
            # Distance of point 2 to line 0-1
            d2 = getdeviation(diffheading(angle_1, angle_B),
                              dist_1, dist_B, dist_2)
            if min(d1, d2) >= 7.0:
                i += 1
                continue

            # Keep closest point to line
            if d2 < d1:
                # Remove point 1
                logo.DEBUG("Discard %s from Z shape %s %s %s %s" % (
                             points[i+1],
                             points[i],
                             points[i+1],
                             points[i+2],
                             points[i+3]))
                angledist[i:i+2] = [ (angle_B, dist_B) ]
                ptsdiscard.append(points[i+1])
                points = points[:i+1] + points[i+2:]
                if i > 0:
                    i -= 1   # recheck with previous point
            else:
                # Remove point 2
                logo.DEBUG("Discard %s from Z shape %s %s %s %s" % (
                             points[i+2],
                             points[i],
                             points[i+1],
                             points[i+2],
                             points[i+3]))
                angledist[i+1:i+3] = [ (angle_A, dist_A) ]
                ptsdiscard.append(points[i+2])
                points = points[:i+2] + points[i+3:]
            continue   # Retry current position (don't increment i)

        #
        # One big angles = V shape
        # 0   2
        #  \ /
        #   1
        #
        angle_0, dist_0 = angledistance(points[i][0], points[i][1],
                                        points[i+2][0], points[i+2][1])
        angle_1, dist_1 = angledist[i]
        angle_2, dist_2 = angledist[i+1]
        # Distance of point 0 to line 1-2
        d1 = getdeviation(diffheading(angle_2, angle_0),
                          dist_2, dist_0, dist_1)
        # Distance of point 2 to line 0-1
        d2 = getdeviation(diffheading(angle_1, angle_0),
                          dist_1, dist_0, dist_2)
        dist_1 = dist_1 * 6371000.0
        dist_2 = dist_2 * 6371000.0

        # Distance for simplification given by length of line 0-1 or 1-2
        # if very big angle
        #   length (smallest)    simplification
        #        < 9m               2.25m
        #       9 to 22m           length/4
        #        > 22m              5.5m
        # if big angle
        #  angle    length (longest)    simplification
        # 105-135      both < 9m           1.25m
        #    "            < 9m             1.9m
        #  90-105      18 to 28m           1.25m
        #    "            > 28m            1.9m
        if abs(diffangle) >= 135.0:
            distmax = min(dist_1, dist_2) * 0.25
            distmax = min(distmax, 5.5)
            distmax = max(distmax, 2.25)
        elif abs(diffangle) >= 105.0:
            if max(dist_1, dist_2) < 9.0:
                distmax = 1.25
            else:
                distmax = 1.9
        else:
            if max(dist_1, dist_2) < 18.0:
                i += 1
                continue
            elif max(dist_1, dist_2) < 28.0:
                distmax = 1.25
            else:
                distmax = 1.9

        if min(d1, d2) < distmax:
            # Remove point 1
            logo.DEBUG("Discard %s from V shape %s %s %s" % (
                         points[i+1],
                         points[i],
                         points[i+1],
                         points[i+2]))
            angledist[i:i+2] = [ (angle_0, dist_0) ]
            ptsdiscard.append(points[i+1])
            points = points[:i+1] + points[i+2:]
            if i > 0:
                i -= 1   # recheck with previous point
            continue

        i += 1

    if ptsdiscard:
        # Some point removed, redo Douglas-Peucker
        points, ptsresimplify = simplifyPoints(points)
        ptsdeleted = ptsdeleted + ptsdiscard + ptsresimplify
    return (points, ptsdeleted)


def diffheading(angle1, angle2):
    """ Return difference of angles in radians. """

    diffangle = angle1 - angle2
    if diffangle < -180:
        diffangle += 360
    elif diffangle > 180:
        diffangle -= 360
    return diffangle


def angledistance(lonsrc, latsrc, londst, latdst):
    """
    Compute heading and distance from (lonsrc, latsrc) to (londst, latdst).
    Return (heading, distance) in radians.
    """

    rlat1 = math.radians(latsrc)
    rlon1 = math.radians(lonsrc)
    rlat2 = math.radians(latdst)
    rlon2 = math.radians(londst)
    head = math.atan2(math.sin(rlon2-rlon1) * math.cos(rlat2),
                      math.cos(rlat1) * math.sin(rlat2) -
                      math.sin(rlat1) * math.cos(rlat2) * math.cos(rlon2-rlon1)
                     ) / math.pi * 180.0
    p = math.sin((rlat2-rlat1)/2)**2 + math.cos(rlat1) * math.cos(rlat2) * math.sin((rlon2-rlon1)/2)**2
    adist = 2 * math.atan2(math.sqrt(p), math.sqrt(1-p))
    return (head, adist)


def getdeviation(diffangle, adist0, adist1, adist2):
    """
    Compute distance (in meters) from point P to line AB.
    Return distance to A or B if projected point doesn't exist on line.
    """

    if abs(diffangle) < 90.0:
        # Compute cross-track error
        e = math.asin(math.sin(adist1)*math.sin(math.radians(diffangle)))
        d = math.acos(math.cos(adist1)/math.cos(e))
        if d > adist0:
            # Point is after line AB, return distance to B
            e=adist2
    else:
        # Point is before line AB, return distance to A
        e=adist1
    return abs(e)*6371000.0


def fixSelfIntersect(points, ptsdeleted):
    """
    Check if line after simplification is self-intersecting.
    Try to remove the self-intersecting condition.
    """

    crossing = findLineIntersection(points)
    if not crossing:
        return (points, ptsdeleted)

    # Simplification process can result in a criss-cross intersection
    # for example a simplified segment going through a peak
    if len(crossing) == 2:
        seg = []
        for segintersect in crossing:
            seg.append(set(segintersect))
        if len(seg[0].intersection(seg[1])) == 1:
            # Same segment criss-crossed by 2 segments with a common vertex
            seg1, seg2 = seg[0].symmetric_difference(seg[1])
            if abs(seg1-seg2) == 1:
                # Delete common vertex from points[1:-1]
                pt = max(seg1, seg2)
                logo.WARN("Fix self-intersect removing %s from line %s and %s"
                          % (points[pt],
                             tuple(points[pt-1:pt+1]),
                             tuple(points[pt:pt+2])))
                ptsdeleted = ptsdeleted + points[pt:pt+1]
                points = points[:pt] + points[pt+1:]
                crossing = findLineIntersection(points)   # recheck
            elif (points[0] == points[-1] and (len(points)-2) in (seg1, seg2)
                  and 0 in (seg1, seg2)):
                # Closed ring and common vertex is the first/last point
                logo.WARN("Fix self-intersect removing %s from line %s and %s"
                          % (points[0],
                             tuple(points[-2:]),
                             tuple(points[0:2])))
                ptsdeleted = ptsdeleted + points[-1:]
                points = points[1:-1] + points[1:2]
                crossing = findLineIntersection(points)   # recheck
    elif len(crossing) == 1:
        # Segment N-1 and N+1 can cross when segment N is going backwards
        for segintersect in crossing:
            seg1, seg2 = segintersect
            if abs(seg1-seg2) == 2:
                # Choose which point to delete
                # keep point closer to intersection
                pt = max(seg1, seg2)
                angl, dist_0 = angledistance(crossing[segintersect][0],
                                             crossing[segintersect][1],
                                             points[pt-1][0],
                                             points[pt-1][1])
                angl, dist_1 = angledistance(crossing[segintersect][0],
                                             crossing[segintersect][1],
                                             points[pt][0],
                                             points[pt][1])
                if dist_0 > dist_1:
                    pt = pt-1
                logo.WARN("Fix self-intersect for line %s and %s removing %s"
                          % (tuple(points[seg1:seg1+2]),
                             tuple(points[seg2:seg2+2]),
                             points[pt]))
                ptsdeleted = ptsdeleted + points[pt:pt+1]
                points = points[:pt] + points[pt+1:]
                crossing = findLineIntersection(points)   # recheck
            elif (points[0] == points[-1] and (
                  ((len(points)-2) in (seg1, seg2) and 1 in (seg1, seg2)) or
                  ((len(points)-3) in (seg1, seg2) and 0 in (seg1, seg2)))
                 ):
                # Closed ring, don't bother to check first/last segment
                # for simplicity point 0 will be simplified
                logo.WARN("Fix self-intersect for line %s and %s removing %s"
                          % (tuple(points[seg1:seg1+2]),
                             tuple(points[seg2:seg2+2]),
                             points[0]))
                ptsdeleted = ptsdeleted + points[-1:]
                points = points[1:-1] + points[1:2]
                crossing = findLineIntersection(points)   # recheck

    # Cannot deal with complexe case
    for segintersect in crossing:
        seg1, seg2 = segintersect
        logo.ERROR("Self-intersect from line %s and %s at %s"
                   % (tuple(points[seg1:seg1+2]),
                      tuple(points[seg2:seg2+2]),
                      crossing[segintersect]))
    return (points, ptsdeleted)


def findLineIntersection(points):
    """
    Find all intersecting segments in a polyline (sweep line algorithm).

    Return a dictionary with a tuple of the 2 intersecting segment number
    as key and the coordinate of the intersection point as value.
    """

    orderedseg = []   # segment encountered by sweep line ordered top to bottom
    crossedseg = []   # keep track of swap needed for crossing segment
    crossings = {}    # list all segments crossing and intersection point

    # Detect and keep crossing tables up to date
    def do_detect_intersection(seg1, seg2):
        if intersect(points[seg1], points[seg1+1],
                     points[seg2], points[seg2+1]):
            if (seg1,seg2) not in crossings and (seg2,seg1) not in crossings:
                # Crossing not already detected
                keyseg = (seg1,seg2)
                coord =  posintersect(points[seg1], points[seg1+1],
                                      points[seg2], points[seg2+1])
                crossings[keyseg] = coord

                # Maintain ordered list, a simple loop will do as we
                # get a very small number of intersection
                i = 0
                while i < len(crossedseg):
                    if cmpcoord(coord, crossedseg[i][0]) < 0:
                        break
                    i += 1
                crossedseg.insert(i, (coord, keyseg))

    # Sort key (sweep line Y or X) depends on bounding box
    x1, y1 = reduce(lambda a,b: (min(a[0], b[0]), min(a[1], b[1])), points)
    x2, y2 = reduce(lambda a,b: (max(a[0], b[0]), max(a[1], b[1])), points)
    if y2-y1 > x2-x1:
        cmpcoord = cmpcoordyx
    else:
        cmpcoord = cmpcoordxy

    # Sort by coord this is our main event queue (crossedseg is
    # the secondary queue for intersection event)
    # No coord duplicate is allowed except for the first and
    # the last point in a closed loop
    isclosedloop = False
    for coord in sorted(points, cmp=cmpcoord):
        segnum = points.index(coord)
        toremove = []
        toinsert = []
        if segnum != 0:
            # Event for end point of previous segment
            if (segnum-1) in orderedseg:
                toremove.append(segnum-1)
            else:
                toinsert.append(segnum-1)
        elif points[0] == points[-1]:
            # Closed line same coord appears twice, do only the first
            if isclosedloop:
                continue
            isclosedloop = True
            if (len(points)-2) in orderedseg:
                toremove.append(len(points)-2)
            else:
                toinsert.append(len(points)-2)

        if segnum != (len(points)-1) :
            # Event for start point of next segment
            if (segnum) in orderedseg:
                toremove.append(segnum)
            else:
                toinsert.append(segnum)

        # Some reordering (swapping) for crossing segment, deal with all past
        # intersection event (when we are beyond the intersection point)
        # for the new upper, test intersection with the predecessor segment
        # for the new lower, test intersection with the successor segment
        while len(crossedseg) > 0:
            if cmpcoord(crossedseg[0][0], coord) > 0:
                break
            seg1, seg2 = crossedseg[0][1]
            crossedseg.pop(0)
            i = orderedseg.index(seg1)
            assert i == orderedseg.index(seg2)-1, (
                   "Cannot swap segment %d <-> %d" % (seg1, seg2) )
            orderedseg[i:i+2] = [ seg2, seg1 ]

            if i > 0:
                do_detect_intersection(orderedseg[i-1], seg2)

            if i+1 < len(orderedseg)-1:
                do_detect_intersection(seg1, orderedseg[i+2])


        # Remove segment who has ended and compare predecessor segment
        # with successor segment for intersection
        for segnum in toremove:
            i = orderedseg.index(segnum)
            if 0 < i < len(orderedseg)-1:
                do_detect_intersection(orderedseg[i-1], orderedseg[i+1])
            del orderedseg[i]


        # Insert new segment and compare with closest (above+below) segment
        for segnum in toinsert:
            i = 0
            while i < len(orderedseg):
                j = orderedseg[i]
                if cmpcoord(points[j], points[j+1]) < 0:
                    pt1 = points[j]
                    pt2 = points[j+1]
                else:
                    pt1 = points[j+1]
                    pt2 = points[j]

                # Special case if 2 segment start at the same point
                if pt1 == coord:
                    if points[segnum] == coord:
                        pt3 = points[segnum+1]
                    else:
                        pt3 = points[segnum]
                    if cmpslope(pt3, pt1, pt2) >= 0:
                        # Slope for this segment greater than ordered segment
                        # (insert it above in the ordered chain)
                        break
                else:
                    if cmpslope(coord, pt1, pt2) >= 0:
                        # coord is above the ordered segment
                        break
                i += 1
            orderedseg.insert(i, segnum)

            if i > 0:
                # Compare with predecessor for intersection
                do_detect_intersection(orderedseg[i-1], segnum)

            if i < len(orderedseg)-1:
                # Compare with successor for intersection
                do_detect_intersection(segnum, orderedseg[i+1])

    return crossings


def cmpcoordxy(a,b):
    """
    Compare coord by X.
    """

    if a[0] < b[0]:
        return -1
    if a[0] > b[0]:
        return 1
    if a[1] < b[1]:
        return -1
    if a[1] > b[1]:
        return 1
    return 0


def cmpcoordyx(a,b):
    """
    Compare coord by Y.
    """

    if a[1] < b[1]:
        return -1
    if a[1] > b[1]:
        return 1
    if a[0] < b[0]:
        return -1
    if a[0] > b[0]:
        return 1
    return 0


def cmpslope(a,b,c):
    """
    Compare slope of AB and BC.

    Return -1 if slope AB < BC, 0 if slope AB = BC, 1 if slope AB > BC.
    """

    slope = (b[0]-a[0])*(c[1]-b[1]) - (c[0]-b[0])*(b[1]-a[1])
    if slope < 0:
        return -1
    elif slope > 0:
        return 1
    return 0


def intersect(a,b,c,d):
    """
    Test if AB and CD intersect.
    """

    if a == c or a == d or b == c or b == d:
        # linked segment never cross
        return False
    if cmpslope(a, c, d) == cmpslope(b, c, d):
        return False
    if cmpslope(c, a, b) == cmpslope(d, a, b):
        return False
    return True


def posintersect(a, b, c, d):
    """
    Return the intersection point of AB and CD.
    Note: do not forget to check if intersection exist (see intersect()
          function) before calling this function.
    """

    # Given the 2 crossing segment ab, cd
    # solve the 2 equations :
    #   (ya-yb)*x + (xb-xa)*y + (xa*yb-xb*ya) = 0
    #   (yc-yd)*x + (xd-xc)*y + (xc*yd-xd*yc) = 0
    coef1A = a[1]-b[1]
    coef1B = b[0]-a[0]
    coef1C = (a[0]*b[1]) - (b[0]*a[1])
    coef2A = c[1]-d[1]
    coef2B = d[0]-c[0]
    coef2C = (c[0]*d[1]) - (d[0]*c[1])
    y = (coef2A*coef1C - coef1A*coef2C) / (coef1A*coef2B - coef2A*coef1B)
    x = (coef1B*coef2C - coef2B*coef1C) / (coef1A*coef2B - coef2A*coef1B)
    return (x, y)
