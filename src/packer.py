"""
packer.py — Triply build volume packing
Simple shelf packer — reliable, no overflow bugs.
Fills X row, then next Y row, then next Z layer.
"""

import numpy as np


def _get_dims_bbox(verts):
    mins=verts.min(axis=0); maxs=verts.max(axis=0)
    return float(maxs[0]-mins[0]),float(maxs[1]-mins[1]),float(maxs[2]-mins[2])


def _get_dims_exact(verts):
    try:
        center=verts.mean(axis=0); centered=verts-center
        _,_,Vt=np.linalg.svd(centered,full_matrices=False)
        proj=centered@Vt.T; dims=proj.max(axis=0)-proj.min(axis=0)
        return float(dims[0]),float(dims[1]),float(dims[2])
    except: return _get_dims_bbox(verts)


def _best_orientation(dx,dy,dz,allow_rot_z=True,allow_rot_xy=False):
    opts={(dx,dy,dz)}
    if allow_rot_z: opts.add((dy,dx,dz))
    if allow_rot_xy: opts.update([(dx,dz,dy),(dz,dx,dy),(dy,dz,dx),(dz,dy,dx)])
    return min(opts,key=lambda o:o[2])


class ShelfPacker3D:
    def __init__(self,bv_x,bv_y,bv_z,part_gap,wall_offset,
                 allow_rot_z=True,allow_rot_xy=False):
        self.bv_x=bv_x; self.bv_y=bv_y; self.bv_z=bv_z
        self.gap=part_gap; self.wo=wall_offset
        self.allow_rot_z=allow_rot_z; self.allow_rot_xy=allow_rot_xy
        wo=wall_offset
        # Boundaries: parts must end before (bv - wall_offset)
        self._ex=bv_x-wo
        self._ey=bv_y-wo
        self._ez=bv_z-wo
        # Cursors start inside wall offset
        self._cx=wo; self._ry=wo; self._lz=wo
        self._rh=0.0; self._lh=0.0
        self.placements=[]; self.overflow=[]

    def pack(self,items,progress_cb=None,cancel_flag=None):
        sorted_items=sorted(items,key=lambda t:t[1]*t[2],reverse=True)
        for item in sorted_items:
            if cancel_flag and cancel_flag[0]: break
            if not self._try(item): self.overflow.append(item)

    def _try(self,item):
        label,dx,dy,dz,data=item
        odx,ody,odz=_best_orientation(dx,dy,dz,self.allow_rot_z,self.allow_rot_xy)
        return self._place((label,odx,ody,odz,data))

    def _place(self,item):
        label,dx,dy,dz,data=item
        g=self.gap; wo=self.wo
        # Try current row
        if self._cx+dx<=self._ex:
            self.placements.append((item,self._cx,self._ry,self._lz))
            self._cx+=dx+g
            self._rh=max(self._rh,dy)
            self._lh=max(self._lh,dz)
            return True
        # New row
        nry=self._ry+self._rh+g
        if nry+dy<=self._ey:
            self._ry=nry; self._rh=0.0; self._cx=wo
            return self._place(item)
        # New layer
        nlz=self._lz+self._lh+g
        if nlz+dz<=self._ez:
            self._lz=nlz; self._lh=0.0
            self._ry=wo; self._rh=0.0; self._cx=wo
            return self._place(item)
        return False


def pack_parts(parts,bv_x,bv_y,bv_z,part_gap=2.0,wall_offset=5.0,
               exact=True,allow_rot_z=True,allow_rot_xy=False,
               progress_cb=None,cancel_flag=None):
    items=[]
    for p in parts:
        v=p['verts']
        dx,dy,dz=_get_dims_exact(v) if exact else _get_dims_bbox(v)
        for i in range(p.get('instances',1)):
            label=f"{p['name']} #{i+1}" if p.get('instances',1)>1 else p['name']
            items.append((label,dx,dy,dz,p))

    all_placements=[]; vol_idx=0; remaining=items
    while remaining:
        if cancel_flag and cancel_flag[0]: break
        packer=ShelfPacker3D(bv_x,bv_y,bv_z,part_gap,wall_offset,
                             allow_rot_z=allow_rot_z,allow_rot_xy=allow_rot_xy)
        packer.pack(remaining,progress_cb=progress_cb,cancel_flag=cancel_flag)
        for item,px,py,pz in packer.placements:
            all_placements.append((item[0],item[4],vol_idx,px,py,pz))
        if not packer.overflow: break
        remaining=packer.overflow; vol_idx+=1
        if vol_idx>50:
            for item in remaining:
                all_placements.append((item[0],item[4],vol_idx,0,0,0))
            break
    return all_placements,vol_idx+1
