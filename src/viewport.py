"""
viewport.py — Triply 3D Viewport
Full rebuild with selection, gizmo, section caps.
"""

import numpy as np
import math
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QRect
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QDragEnterEvent, QDropEvent
from OpenGL.GL import *


def _perspective(fov, aspect, near, far):
    f = 1.0 / np.tan(np.radians(fov) / 2.0)
    m = np.zeros((4,4), dtype=np.float32)
    m[0,0]=f/aspect; m[1,1]=f
    m[2,2]=(far+near)/(near-far); m[2,3]=(2*far*near)/(near-far)
    m[3,2]=-1.0
    return m


class Viewport3D(QOpenGLWidget):
    part_clicked  = pyqtSignal(int)
    files_dropped = pyqtSignal(list)
    empty_clicked = pyqtSignal()
    mesh_moved    = pyqtSignal(int, float, float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        from PyQt6.QtGui import QSurfaceFormat
        fmt = QSurfaceFormat()
        fmt.setDepthBufferSize(24)
        fmt.setStencilBufferSize(8)
        fmt.setSamples(4)
        self.setFormat(fmt)
        self.setMinimumSize(400, 300)
        from PyQt6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAcceptDrops(True)

        self._rot_x     = -90.0
        self._rot_y     =   0.0
        self._zoom      = 350.0
        self._pan_x     =   0.0
        self._pan_y     =   0.0
        self._last_pos  = QPoint()
        self._mouse_btn = None
        self._drag_dist = 0
        self._width     = 1
        self._height    = 1

        self._orbit_btn = Qt.MouseButton.RightButton
        self._pan_btn   = Qt.MouseButton.MiddleButton

        self._meshes    = {}
        self._next_idx  = 0
        self._selected  = -1
        self._bv_list   = []
        self._show_bv   = True
        self._layer_pct = 1.0
        self._wireframe = False
        self._ortho     = False
        self._show_grid = True

        # Gizmo
        self._gizmo_active          = False
        self._gizmo_center          = None
        self._gizmo_drag_axis       = None
        self._gizmo_drag_start      = None
        self._gizmo_mesh_offset_start = None
        self._gizmo_size            = 40.0

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------
    def set_mouse_mapping(self, orbit, pan):
        self._orbit_btn = orbit; self._pan_btn = pan

    def set_layer_clip(self, pct):
        self._layer_pct = max(0.0, min(1.0, pct)); self.update()

    def set_show_build_volume(self, show):
        self._show_bv = show; self.update()

    def set_selected(self, idx):
        self._selected = idx
        if idx >= 0 and idx in self._meshes:
            mesh = self._meshes[idx]
            v    = mesh['verts'] + mesh['offset']
            self._gizmo_center = (v.max(axis=0) + v.min(axis=0)) / 2.0
            self._gizmo_active = True
        else:
            self._gizmo_active = False
            self._gizmo_center = None
        self.update()

    def clear_build_volumes(self):
        self._bv_list.clear(); self.update()

    def add_build_volume(self, x, y, z, offset_x=0.0, label=""):
        self._bv_list.append((x,y,z,offset_x,label)); self.update()

    # ------------------------------------------------------------------
    # Mesh API
    # ------------------------------------------------------------------
    def add_mesh(self, vertices, faces, color=(0.65,0.65,0.65)):
        normals = self._compute_normals(vertices, faces)
        idx = self._next_idx; self._next_idx += 1
        self._meshes[idx] = {
            'verts':   np.ascontiguousarray(vertices, dtype=np.float32),
            'normals': np.ascontiguousarray(normals,  dtype=np.float32),
            'faces':   np.ascontiguousarray(faces,    dtype=np.int32),
            'color':   color, 'visible': True,
            'offset':  np.zeros(3, dtype=np.float32), 'alpha': 1.0,
        }
        self.update(); return idx

    def remove_mesh(self, idx):
        if idx in self._meshes: del self._meshes[idx]; self.update()

    def update_mesh(self, idx, vertices, faces):
        if idx in self._meshes:
            normals = self._compute_normals(vertices, faces)
            self._meshes[idx]['verts']   = np.ascontiguousarray(vertices, dtype=np.float32)
            self._meshes[idx]['normals'] = np.ascontiguousarray(normals,  dtype=np.float32)
            self._meshes[idx]['faces']   = np.ascontiguousarray(faces,    dtype=np.int32)
            if self._selected == idx:
                v = self._meshes[idx]['verts'] + self._meshes[idx]['offset']
                self._gizmo_center = (v.max(axis=0)+v.min(axis=0))/2.0
            self.update()

    def set_mesh_color(self, idx, color):
        if idx in self._meshes: self._meshes[idx]['color']=color; self.update()

    def set_mesh_offset(self, idx, x, y, z):
        if idx in self._meshes:
            self._meshes[idx]['offset'] = np.array([x,y,z], dtype=np.float32)
            if self._selected == idx:
                v = self._meshes[idx]['verts'] + self._meshes[idx]['offset']
                self._gizmo_center = (v.max(axis=0)+v.min(axis=0))/2.0
            self.update()

    def set_mesh_visible(self, idx, v):
        if idx in self._meshes: self._meshes[idx]['visible']=v; self.update()

    def set_mesh_alpha(self, idx, a):
        if idx in self._meshes: self._meshes[idx]['alpha']=float(a); self.update()

    def clear_meshes(self):
        self._meshes.clear(); self._next_idx=0; self.update()

    # ------------------------------------------------------------------
    # OpenGL
    # ------------------------------------------------------------------
    def initializeGL(self):
        glClearColor(0.07,0.07,0.08,1.0)
        glEnable(GL_DEPTH_TEST); glDepthFunc(GL_LESS); glDepthMask(GL_TRUE)
        glDisable(GL_BLEND); glDisable(GL_CULL_FACE)
        glEnable(GL_LIGHTING); glEnable(GL_LIGHT0); glEnable(GL_LIGHT1)
        glLightModeli(GL_LIGHT_MODEL_TWO_SIDE, GL_TRUE)
        glLightModelfv(GL_LIGHT_MODEL_AMBIENT, [0.15,0.15,0.15,1.0])
        glLightfv(GL_LIGHT0, GL_POSITION, [1.0,1.5,2.0,0.0])
        glLightfv(GL_LIGHT0, GL_DIFFUSE,  [0.80,0.80,0.80,1.0])
        glLightfv(GL_LIGHT0, GL_SPECULAR, [0.20,0.20,0.20,1.0])
        glLightfv(GL_LIGHT0, GL_AMBIENT,  [0.0,0.0,0.0,1.0])
        glLightfv(GL_LIGHT1, GL_POSITION, [-1.0,-0.8,-0.5,0.0])
        glLightfv(GL_LIGHT1, GL_DIFFUSE,  [0.30,0.30,0.32,1.0])
        glLightfv(GL_LIGHT1, GL_AMBIENT,  [0.0,0.0,0.0,1.0])
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
        glMaterialfv(GL_FRONT_AND_BACK, GL_SPECULAR,  [0.1,0.1,0.1,1.0])
        glMaterialf (GL_FRONT_AND_BACK, GL_SHININESS, 10.0)
        glMaterialfv(GL_FRONT_AND_BACK, GL_EMISSION,  [0.0,0.0,0.0,1.0])
        glShadeModel(GL_SMOOTH); glEnable(GL_NORMALIZE)
        glHint(GL_POLYGON_SMOOTH_HINT, GL_NICEST)
        glEnable(GL_POLYGON_SMOOTH)
        glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)
        glEnable(GL_LINE_SMOOTH)

    def resizeGL(self, w, h):
        dpr = self.devicePixelRatio()
        self._width  = max(int(w*dpr), 1)
        self._height = max(int(h*dpr), 1)
        self._rebuild_projection()

    def _rebuild_projection(self):
        # Use actual framebuffer size for correct rendering on all displays
        dpr = self.devicePixelRatio()
        w = max(int(self.width()  * dpr), 1)
        h = max(int(self.height() * dpr), 1)
        self._width  = w
        self._height = h
        glViewport(0, 0, w, h)
        glMatrixMode(GL_PROJECTION); glLoadIdentity()
        aspect = w / h
        if self._ortho:
            scale = self._zoom*0.005
            glOrtho(-scale*aspect,scale*aspect,-scale,scale,-10000,10000)
        else:
            pm = _perspective(45.0, aspect, 0.1, 10000.0)
            glLoadMatrixf(pm.T)
        glMatrixMode(GL_MODELVIEW)

    def paintGL(self):
        if not self.isValid() or not self.context() or not self.context().isValid():
            return
        self._rebuild_projection()
        glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        glTranslatef(self._pan_x, self._pan_y, -self._zoom)
        glRotatef(self._rot_x, 1,0,0)
        glRotatef(self._rot_y, 0,0,1)

        # Layer clip — only affects meshes
        if self._layer_pct < 1.0 and self._bv_list:
            bz = self._bv_list[0][2]
            glEnable(GL_CLIP_PLANE0)
            glClipPlane(GL_CLIP_PLANE0, [0,0,-1, bz*self._layer_pct])
        else:
            glDisable(GL_CLIP_PLANE0)

        # Draw meshes back-to-front
        glDisable(GL_BLEND); glDepthMask(GL_TRUE)
        glEnable(GL_DEPTH_TEST); glDepthFunc(GL_LESS)
        rx = math.radians(self._rot_x); ry = math.radians(self._rot_y)
        cam_fwd = np.array([
            math.sin(ry)*math.cos(rx), -math.sin(rx),
            -math.cos(ry)*math.cos(rx)
        ])
        def mesh_depth(item):
            idx,mesh=item; v=mesh['verts']
            c=(v.max(axis=0)+v.min(axis=0))/2.0+mesh['offset']
            return -float(np.dot(c,cam_fwd))
        for idx,mesh in sorted(self._meshes.items(), key=mesh_depth):
            if not mesh['visible']: continue
            glPushMatrix(); glTranslatef(*mesh['offset'])
            self._draw_mesh(mesh, idx==self._selected)
            glPopMatrix()

        glDisable(GL_CLIP_PLANE0)

        # Grid and BV always visible (no clip)
        if self._show_bv and self._bv_list:
            for bv in self._bv_list: self._draw_grid_bv(*bv)
            for bv in self._bv_list: self._draw_bv(*bv)
        else:
            self._draw_grid_world()

        self._draw_axes()

        # Section caps
        if self._layer_pct < 1.0 and self._bv_list:
            self._draw_section_caps()

        # Gizmo
        if self._gizmo_active and self._gizmo_center is not None:
            glDisable(GL_DEPTH_TEST)
            self._draw_gizmo()
            glEnable(GL_DEPTH_TEST)

    def _draw_mesh(self, mesh, selected):
        r,g,b = mesh['color']
        if selected:
            r=min(1.0,r*1.4+0.1); g=min(1.0,g*1.4+0.1); b=min(1.0,b*1.4+0.1)
        if self._wireframe:
            glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
        # Use immediate mode (glBegin/glEnd) — works in all frozen contexts
        import numpy as _np
        verts = mesh['verts']; normals = mesh['normals']; faces = mesh['faces']
        glColor3f(r,g,b)
        glBegin(GL_TRIANGLES)
        for tri in faces:
            for vi in tri:
                glNormal3f(float(normals[vi,0]),float(normals[vi,1]),float(normals[vi,2]))
                glVertex3f(float(verts[vi,0]),float(verts[vi,1]),float(verts[vi,2]))
        glEnd()
        if self._wireframe:
            glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)

    def _draw_bv(self, bx, by, bz, ox, label):
        glDisable(GL_LIGHTING); glColor3f(0.54,0.08,0.08); glLineWidth(1.2)
        c=[(ox,0,0),(ox+bx,0,0),(ox+bx,by,0),(ox,by,0),
           (ox,0,bz),(ox+bx,0,bz),(ox+bx,by,bz),(ox,by,bz)]
        glBegin(GL_LINES)
        for a,b in [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)]:
            glVertex3fv(c[a]); glVertex3fv(c[b])
        glEnd(); glLineWidth(1.0); glEnable(GL_LIGHTING)

    def _draw_grid_bv(self, bx, by, bz, ox, label):
        glDisable(GL_LIGHTING)
        size=min(bx,by)
        step=5 if size<=50 else 10 if size<=200 else 25 if size<=500 else 50
        glColor3f(0.16,0.14,0.14); glBegin(GL_LINES)
        xv=0.0
        while xv<=bx+1e-6:
            x=min(xv,bx); glVertex3f(ox+x,0,0); glVertex3f(ox+x,by,0); xv+=step
        yv=0.0
        while yv<=by+1e-6:
            y=min(yv,by); glVertex3f(ox,y,0); glVertex3f(ox+bx,y,0); yv+=step
        glVertex3f(ox+bx,0,0); glVertex3f(ox+bx,by,0)
        glVertex3f(ox,by,0);   glVertex3f(ox+bx,by,0)
        glEnd(); glEnable(GL_LIGHTING)

    def _draw_grid_world(self):
        glDisable(GL_LIGHTING); glColor3f(0.14,0.12,0.12); glBegin(GL_LINES)
        for i in range(-400,410,10):
            glVertex3f(i,-400,0); glVertex3f(i,400,0)
            glVertex3f(-400,i,0); glVertex3f(400,i,0)
        glEnd(); glEnable(GL_LIGHTING)

    def _draw_axes(self):
        glDisable(GL_LIGHTING); glLineWidth(4.0); glBegin(GL_LINES)
        glColor3f(1.0,0.15,0.15); glVertex3f(0,0,0); glVertex3f(40,0,0)
        glColor3f(0.15,1.0,0.15); glVertex3f(0,0,0); glVertex3f(0,40,0)
        glColor3f(0.15,0.35,1.0); glVertex3f(0,0,0); glVertex3f(0,0,40)
        glEnd(); glPointSize(8.0); glBegin(GL_POINTS)
        glColor3f(1.0,0.15,0.15); glVertex3f(40,0,0)
        glColor3f(0.15,1.0,0.15); glVertex3f(0,40,0)
        glColor3f(0.15,0.35,1.0); glVertex3f(0,0,40)
        glEnd(); glPointSize(1.0); glLineWidth(1.0); glEnable(GL_LIGHTING)

    def _draw_section_caps(self):
        """
        Correct stencil-buffer section fill.
        Uses two-pass stencil: render mesh caps into stencil, 
        then draw filled quad only where stencil is set.
        """
        import numpy as _np
        if not self._bv_list: return
        bz = float(self._bv_list[0][2])
        clip_z = bz * self._layer_pct
        z_cap = clip_z + 0.005

        pastels = [
            (0.72,0.85,0.95),(0.95,0.75,0.72),(0.75,0.95,0.75),
            (0.95,0.92,0.72),(0.88,0.75,0.95),(0.72,0.95,0.92),
        ]

        glDisable(GL_LIGHTING)
        glDisable(GL_CLIP_PLANE0)

        for mesh_i,(idx_m,mesh) in enumerate(self._meshes.items()):
            if not mesh['visible']: continue
            v = mesh['verts'] + mesh['offset']
            faces = mesh['faces']
            r,g,b = pastels[mesh_i % len(pastels)]

            # Bounding box for full cap quad
            xmin,xmax = float(v[:,0].min())-1, float(v[:,0].max())+1
            ymin,ymax = float(v[:,1].min())-1, float(v[:,1].max())+1

            # Get clipped cap triangles
            z0=v[faces[:,0],2]; z1=v[faces[:,1],2]; z2=v[faces[:,2],2]
            crossing = ((z0>clip_z)|(z1>clip_z)|(z2>clip_z)) &                        ((z0<=clip_z)|(z1<=clip_z)|(z2<=clip_z))
            cross_idx = _np.where(crossing)[0]

            cap_polys = []
            cut_segs = []
            for fi in cross_idx:
                tri = faces[fi]
                pts = [(float(v[tri[i],0]),float(v[tri[i],1]),
                        float(v[tri[i],2])) for i in range(3)]
                clipped=[]; intersect_pts=[]
                for i in range(3):
                    cur=pts[i]; nxt=pts[(i+1)%3]
                    if cur[2]<=clip_z: clipped.append((cur[0],cur[1]))
                    if (cur[2]<=clip_z)!=(nxt[2]<=clip_z):
                        t=(clip_z-cur[2])/(nxt[2]-cur[2]+1e-10)
                        ix=cur[0]+t*(nxt[0]-cur[0])
                        iy=cur[1]+t*(nxt[1]-cur[1])
                        clipped.append((ix,iy))
                        intersect_pts.append((ix,iy))
                if len(clipped)>=3: cap_polys.append(clipped)
                if len(intersect_pts)==2: cut_segs.extend(intersect_pts)

            if not cap_polys: continue

            # ── PASS 1: Write cap triangles to stencil ────────────────────────
            glEnable(GL_STENCIL_TEST)
            glClear(GL_STENCIL_BUFFER_BIT)
            glColorMask(False,False,False,False)
            glDepthMask(False)
            glDisable(GL_DEPTH_TEST)
            glDisable(GL_CULL_FACE)
            glStencilFunc(GL_ALWAYS, 0, 0xFF)
            glStencilOp(GL_KEEP, GL_KEEP, GL_INVERT)

            # Draw cap polygons into stencil — front faces toggle stencil bit
            glBegin(GL_TRIANGLES)
            for poly in cap_polys:
                for i in range(1,len(poly)-1):
                    glVertex3f(poly[0][0],poly[0][1],z_cap)
                    glVertex3f(poly[i][0],poly[i][1],z_cap)
                    glVertex3f(poly[i+1][0],poly[i+1][1],z_cap)
            glEnd()

            # NOTE: We do NOT draw all-below triangles into the stencil.
            # That approach only works for convex solid meshes. For lattice/hollow
            # meshes (gyroid etc.) the inner faces cancel the outer via GL_INVERT,
            # producing a solid-looking fill instead of showing wall thickness.
            # The crossing triangles alone correctly define the section boundary
            # for both solid and hollow meshes.

            # ── PASS 2: Draw fill where stencil != 0 ─────────────────────────
            glColorMask(True,True,True,True)
            glDepthMask(True)
            glStencilFunc(GL_NOTEQUAL, 0, 0xFF)
            glStencilOp(GL_KEEP, GL_KEEP, GL_KEEP)
            glColor3f(r,g,b)
            glBegin(GL_QUADS)
            glVertex3f(xmin,ymin,z_cap+0.001)
            glVertex3f(xmax,ymin,z_cap+0.001)
            glVertex3f(xmax,ymax,z_cap+0.001)
            glVertex3f(xmin,ymax,z_cap+0.001)
            glEnd()

            # ── PASS 3: Hatch over fill ───────────────────────────────────────
            glStencilFunc(GL_NOTEQUAL, 0, 0xFF)
            hr,hg,hb=r*0.6,g*0.6,b*0.6
            glColor3f(hr,hg,hb)
            glLineWidth(0.75)
            hz=z_cap+0.003
            spacing=2.0
            glBegin(GL_LINES)
            span_=max(xmax-xmin,ymax-ymin)*2
            d=xmin-span_
            while d<xmax+span_:
                glVertex3f(d,ymin,hz); glVertex3f(d+(ymax-ymin),ymax,hz)
                d+=spacing
            glEnd()
            glLineWidth(1.0)
            glDisable(GL_STENCIL_TEST)

            # ── PASS 4: Cut edge outline ──────────────────────────────────────
            glEnable(GL_DEPTH_TEST)
            glColor3f(0.05,0.05,0.05)
            glLineWidth(2.0)
            glBegin(GL_LINES)
            for i in range(0,len(cut_segs)-1,2):
                x1,y1=cut_segs[i]; x2,y2=cut_segs[i+1]
                glVertex3f(x1,y1,z_cap+0.01)
                glVertex3f(x2,y2,z_cap+0.01)
            glEnd()
            glLineWidth(1.0)

        glEnable(GL_DEPTH_TEST); glDepthFunc(GL_LESS)
        glEnable(GL_LIGHTING); glEnable(GL_CLIP_PLANE0)
        glEnable(GL_CULL_FACE)
    def _clip_line_to_polygon(self, x1,y1,x2,y2, poly):
        t_enter=0.0; t_exit=1.0; dx=x2-x1; dy=y2-y1; n=len(poly)
        for i in range(n):
            ex1,ey1=poly[i]; ex2,ey2=poly[(i+1)%n]
            enx=ey2-ey1; eny=-(ex2-ex1)
            denom=enx*dx+eny*dy; numer=enx*(x1-ex1)+eny*(y1-ey1)
            if abs(denom)<1e-10:
                if numer<0: return []
            elif denom<0:
                t=-numer/denom; t_enter=max(t_enter,t)
            else:
                t=-numer/denom; t_exit=min(t_exit,t)
            if t_enter>t_exit: return []
        if t_enter>t_exit: return []
        return [(x1+t_enter*dx,y1+t_enter*dy,x1+t_exit*dx,y1+t_exit*dy)]

    # ------------------------------------------------------------------
    # View cube
    # ------------------------------------------------------------------
    def paintEvent(self, event):
        super().paintEvent(event)

    def _draw_gizmo(self):
        if self._gizmo_center is None: return
        cx,cy,cz=self._gizmo_center; sz=self._gizmo_size
        hl=sz*0.22; hw=sz*0.08
        glDisable(GL_LIGHTING); glLineWidth(3.0)
        axes=[
            ('X',(cx,cy,cz),(cx+sz,cy,cz),   (1.0,0.15,0.15),self._gizmo_drag_axis=='X'),
            ('Y',(cx,cy,cz),(cx,cy+sz,cz),   (0.15,1.0,0.15),self._gizmo_drag_axis=='Y'),
            ('Z',(cx,cy,cz),(cx,cy,cz+sz),(0.15,0.35,1.0),self._gizmo_drag_axis=='Z'),
        ]
        for axis,start,end,color,active in axes:
            r,g,b=color
            if active: r=min(1.0,r+0.4); g=min(1.0,g+0.4); b=min(1.0,b+0.4)
            glColor3f(r,g,b); glBegin(GL_LINES); glVertex3fv(start); glVertex3fv(end); glEnd()
            ex,ey,ez=end; sx,sy,sz_=start
            dx,dy,dz=ex-sx,ey-sy,ez-sz_; ln=(dx*dx+dy*dy+dz*dz)**0.5
            if ln<1e-6: continue
            dx/=ln; dy/=ln; dz/=ln
            d=np.array([dx,dy,dz]); up=np.array([0,0,1]) if abs(dz)<0.9 else np.array([0,1,0])
            p1=np.cross(d,up); p1/=np.linalg.norm(p1)
            p2=np.cross(d,p1); p2/=np.linalg.norm(p2)
            bx_=ex-dx*hl; by_=ey-dy*hl; bz_=ez-dz*hl
            pts=[(bx_+p1[0]*hw,by_+p1[1]*hw,bz_+p1[2]*hw),
                 (bx_+p2[0]*hw,by_+p2[1]*hw,bz_+p2[2]*hw),
                 (bx_-p1[0]*hw,by_-p1[1]*hw,bz_-p1[2]*hw),
                 (bx_-p2[0]*hw,by_-p2[1]*hw,bz_-p2[2]*hw)]
            glBegin(GL_TRIANGLE_FAN); glVertex3f(ex,ey,ez)
            for pt in pts+[pts[0]]: glVertex3fv(pt)
            glEnd()
        glPointSize(10.0); glColor3f(0.9,0.9,0.9)
        glBegin(GL_POINTS); glVertex3f(cx,cy,cz); glEnd()
        glPointSize(1.0); glLineWidth(1.0); glEnable(GL_LIGHTING)

    def _gizmo_hit_test(self, screen_x, screen_y):
        if not self._gizmo_active or self._gizmo_center is None: return None
        cx,cy,cz=self._gizmo_center; sz=self._gizmo_size
        tips={'X':np.array([cx+sz,cy,cz]),'Y':np.array([cx,cy+sz,cz]),'Z':np.array([cx,cy,cz+sz])}
        c_s=self._world_to_screen(cx,cy,cz)
        if c_s is None: return None
        THRESHOLD=14
        for axis,tip in tips.items():
            tip_s=self._world_to_screen(*tip)
            if tip_s is None: continue
            ax,ay=c_s; bx,by=tip_s; mx,my=screen_x,screen_y
            dx,dy=bx-ax,by-ay; ln2=dx*dx+dy*dy
            if ln2<1e-6: continue
            t=max(0.0,min(1.0,((mx-ax)*dx+(my-ay)*dy)/ln2))
            px=ax+t*dx-mx; py=ay+t*dy-my
            if (px*px+py*py)**0.5<THRESHOLD: return axis
        return None

    def _world_to_screen(self, wx, wy, wz):
        try:
            aspect=self._width/self._height
            pm=_perspective(45.0,aspect,0.1,10000.0)
            rx=np.radians(self._rot_x); ry=np.radians(self._rot_y)
            cx,sx=np.cos(rx),np.sin(rx); cy,sy=np.cos(ry),np.sin(ry)
            Rx=np.array([[1,0,0,0],[0,cx,-sx,0],[0,sx,cx,0],[0,0,0,1]],dtype=np.float32)
            Rz=np.array([[cy,-sy,0,0],[sy,cy,0,0],[0,0,1,0],[0,0,0,1]],dtype=np.float32)
            T=np.array([[1,0,0,self._pan_x],[0,1,0,self._pan_y],[0,0,1,-self._zoom],[0,0,0,1]],dtype=np.float32)
            mv=T@Rx@Rz; pt=np.array([wx,wy,wz,1.0],dtype=np.float32)
            clip=pm@mv@pt
            if abs(clip[3])<1e-6: return None
            ndc=clip[:3]/clip[3]
            if not(-1<=ndc[0]<=1 and -1<=ndc[1]<=1): return None
            return (int((ndc[0]+1)/2*self._width), int((1-ndc[1])/2*self._height))
        except: return None

    # ------------------------------------------------------------------
    # Mouse
    # ------------------------------------------------------------------
    def mousePressEvent(self, event):
        self._last_pos=event.position().toPoint()
        self._mouse_btn=event.button(); self._drag_dist=0
        if event.button()==Qt.MouseButton.LeftButton:
            pos=event.position().toPoint()
            axis=self._gizmo_hit_test(pos.x(),pos.y())
            if axis:
                self._gizmo_drag_axis=axis
                self._gizmo_drag_start=pos
                if self._selected in self._meshes:
                    self._gizmo_mesh_offset_start=self._meshes[self._selected]['offset'].copy()
                self._mouse_btn=None; self.update(); return

    def mouseMoveEvent(self, event):
        pos=event.position().toPoint()
        dx=pos.x()-self._last_pos.x(); dy=pos.y()-self._last_pos.y()
        self._drag_dist+=abs(dx)+abs(dy)
        if self._gizmo_drag_axis and self._gizmo_drag_start is not None:
            self._handle_gizmo_drag(pos); self._last_pos=pos; return
        if self._mouse_btn==self._orbit_btn:
            self._rot_y+=dx*0.5; self._rot_x+=dy*0.5
        elif self._mouse_btn==self._pan_btn:
            self._pan_x+=dx*0.3; self._pan_y-=dy*0.3
        self._last_pos=pos; self.update()

    def _handle_gizmo_drag(self, pos):
        if self._selected not in self._meshes: return
        if self._gizmo_mesh_offset_start is None: return
        start_pos=self._gizmo_drag_start
        dx_screen=pos.x()-start_pos.x(); dy_screen=pos.y()-start_pos.y()
        cx,cy,cz=self._gizmo_center; sz=self._gizmo_size; axis=self._gizmo_drag_axis
        if axis=='X':   wt=(cx+sz,cy,cz)
        elif axis=='Y': wt=(cx,cy+sz,cz)
        else:           wt=(cx,cy,cz+sz)
        c_s=self._world_to_screen(cx,cy,cz); t_s=self._world_to_screen(*wt)
        if c_s is None or t_s is None: return
        ax_s=np.array([t_s[0]-c_s[0],t_s[1]-c_s[1]],dtype=np.float32)
        ax_len=np.linalg.norm(ax_s)
        if ax_len<1e-6: return
        ax_s/=ax_len
        proj=np.dot(np.array([dx_screen,dy_screen],dtype=np.float32),ax_s)
        wd=proj*sz/ax_len
        off=self._gizmo_mesh_offset_start.copy()
        if axis=='X': off[0]+=wd
        elif axis=='Y': off[1]+=wd
        else: off[2]+=wd
        # Clamp to build volume if set
        if self._bv_list:
            bx,by,bz=self._bv_list[0][0],self._bv_list[0][1],self._bv_list[0][2]
            v0=self._meshes[self._selected]['verts']
            dx=float(v0[:,0].max()-v0[:,0].min())
            dy=float(v0[:,1].max()-v0[:,1].min())
            dz=float(v0[:,2].max()-v0[:,2].min())
            if dx<=bx and dy<=by and dz<=bz:
                off[0]=float(np.clip(off[0], 0, bx-dx))
                off[1]=float(np.clip(off[1], 0, by-dy))
                off[2]=float(np.clip(off[2], 0, bz-dz))
            else:
                off[2]=float(max(0.0, off[2]))
        else:
            off[2]=float(max(0.0, off[2]))
        self._meshes[self._selected]['offset']=off
        v=self._meshes[self._selected]['verts']+off
        self._gizmo_center=(v.max(axis=0)+v.min(axis=0))/2.0
        self.mesh_moved.emit(self._selected,float(off[0]),float(off[1]),float(off[2]))
        self.update()

    def mouseReleaseEvent(self, event):
        if self._gizmo_drag_axis:
            self._gizmo_drag_axis=None; self._gizmo_drag_start=None
            self._gizmo_mesh_offset_start=None; self.update(); return
        if self._drag_dist<5:
            pos=event.position().toPoint()
            hit=self._try_select(pos)
            if not hit: self.empty_clicked.emit()
        self._mouse_btn=None; self._drag_dist=0

    def wheelEvent(self, event):
        self._zoom=max(10,self._zoom-event.angleDelta().y()*0.3); self.update()

    # ------------------------------------------------------------------
    # Selection — Möller–Trumbore per-triangle ray test
    # ------------------------------------------------------------------
    def _try_select(self, pos):
        if not self._meshes: return False
        ro,rd=self._unproject_ray(pos.x(),pos.y())
        if rd is None: return False
        best_t=-1; best_idx=-1
        for idx,mesh in self._meshes.items():
            if not mesh['visible']: continue
            v=mesh['verts']+mesh['offset']; f=mesh['faces']
            # AABB cull
            t_aabb=self._ray_aabb(ro,rd,v.min(axis=0),v.max(axis=0))
            if t_aabb is None: continue
            # Per-triangle
            t_tri=self._ray_mesh_mt(ro,rd,v,f)
            if t_tri is not None and (best_t<0 or t_tri<best_t):
                best_t=t_tri; best_idx=idx
        if best_idx>=0:
            self.part_clicked.emit(best_idx); return True
        return False

    def _unproject_ray(self, x, y):
        try:
            self.makeCurrent()
            mv  = np.array(glGetDoublev(GL_MODELVIEW_MATRIX),  dtype=np.float64)
            prj = np.array(glGetDoublev(GL_PROJECTION_MATRIX), dtype=np.float64)
            viewport = np.array(glGetIntegerv(GL_VIEWPORT), dtype=np.float64)

            # Scale logical pixel coords to physical pixels for HiDPI displays
            dpr = self.devicePixelRatio()
            x = x * dpr
            y = y * dpr
            yi = float(self._height - y)

            def unproj(wz):
                ndc = np.array([
                    (x    - viewport[0]) / viewport[2] * 2.0 - 1.0,
                    (yi   - viewport[1]) / viewport[3] * 2.0 - 1.0,
                    wz * 2.0 - 1.0, 1.0
                ])
                clip_inv = np.linalg.inv(prj.T) @ ndc
                if abs(clip_inv[3]) < 1e-10: return None
                clip_inv /= clip_inv[3]
                world = np.linalg.inv(mv.T) @ clip_inv
                if abs(world[3]) < 1e-10: return None
                return (world[:3] / world[3]).astype(np.float32)

            near = unproj(0.0)
            far  = unproj(1.0)
            if near is None or far is None: return None, None

            rd = far - near
            n  = np.linalg.norm(rd)
            if n < 1e-10: return None, None
            rd /= n
            return near, rd
        except Exception as e:
            return None, None


    def _ray_mesh_mt(self, ro, rd, verts, faces):
        """Möller–Trumbore vectorized ray-triangle intersection."""
        EPS=1e-7
        v0=verts[faces[:,0]].astype(np.float64)
        v1=verts[faces[:,1]].astype(np.float64)
        v2=verts[faces[:,2]].astype(np.float64)
        rd_=np.array(rd,dtype=np.float64)
        ro_=np.array(ro,dtype=np.float64)
        e1=v1-v0; e2=v2-v0
        h=np.cross(rd_[None,:],e2); a=(e1*h).sum(axis=1)
        valid=np.abs(a)>EPS
        if not valid.any(): return None
        f_inv=np.where(valid,1.0/np.where(valid,a,1.0),0.0)
        s=ro_[None,:]-v0; u=f_inv*(s*h).sum(axis=1)
        valid&=(u>=0.0)&(u<=1.0)
        q=np.cross(s,e1); vv=f_inv*(rd_[None,:]*q).sum(axis=1)
        valid&=(vv>=0.0)&(u+vv<=1.0)
        t=f_inv*(e2*q).sum(axis=1); valid&=t>EPS
        if not valid.any(): return None
        t_vals=np.where(valid,t,np.inf)
        min_t=float(t_vals.min())
        return min_t if min_t<np.inf else None

    def _ray_aabb(self, orig, d, bmin, bmax):
        tmin,tmax=-np.inf,np.inf
        for i in range(3):
            if abs(d[i])<1e-8:
                if orig[i]<bmin[i] or orig[i]>bmax[i]: return None
            else:
                t1=(bmin[i]-orig[i])/d[i]; t2=(bmax[i]-orig[i])/d[i]
                tmin=max(tmin,min(t1,t2)); tmax=min(tmax,max(t1,t2))
        if tmax<tmin or tmax<0: return None
        return tmin if tmin>=0 else tmax

    # ------------------------------------------------------------------
    # Drag and drop
    # ------------------------------------------------------------------
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls(): event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        paths=[u.toLocalFile() for u in event.mimeData().urls()
               if u.toLocalFile().lower().endswith(('.stl','.3mf','.step','.stp'))]
        if paths: self.files_dropped.emit(paths)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _compute_normals(self, verts, faces):
        n=np.zeros_like(verts,dtype=np.float64)
        v0=verts[faces[:,0]]; v1=verts[faces[:,1]]; v2=verts[faces[:,2]]
        fn=np.cross(v1-v0,v2-v0)
        for i in range(3): np.add.at(n,faces[:,i],fn)
        norms=np.linalg.norm(n,axis=1,keepdims=True); norms[norms==0]=1
        return (n/norms).astype(np.float32)

    def _fit_view(self):
        if not self._meshes: return
        all_v=np.vstack([m['verts'] for m in self._meshes.values()])
        center=(all_v.max(axis=0)+all_v.min(axis=0))/2
        span=np.linalg.norm(all_v.max(axis=0)-all_v.min(axis=0))
        self._zoom=max(50,span*1.8)
        self._pan_x=-center[0]*0.3; self._pan_y=-center[2]*0.3

    def fit_to_volume(self, bv_x, bv_y, bv_z):
        self._rot_x = -90.0
        self._rot_y =   0.0

        # Use logical widget size for camera math (dpr handled in projection)
        w = max(self.width(),  1)
        h = max(self.height(), 1)
        aspect = w / h

        # With 45deg FOV: visible_half_h = zoom * tan(22.5deg) = zoom * 0.4142
        # Fit bv_z vertically with 20% padding
        zoom_for_h = (bv_z / (2.0 * 0.4142)) * 1.2
        # Fit bv_x horizontally accounting for aspect ratio
        zoom_for_w = (bv_x / (2.0 * 0.4142 * aspect)) * 1.2
        self._zoom  = max(zoom_for_h, zoom_for_w, 50.0)

        # Center: build volume goes from 0..bv_x in X, 0..bv_z in Z
        self._pan_x = -(bv_x / 2.0)
        self._pan_y = -(bv_z / 2.0)
        self.update()
