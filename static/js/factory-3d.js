import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const container = document.querySelector("#factory-scene");
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x9bcbe3);
scene.fog = new THREE.FogExp2(0xb9d4dc, 0.00085);

const camera = new THREE.PerspectiveCamera(42, innerWidth / innerHeight, 0.1, 600);
const HOME_CAMERA = new THREE.Vector3(-32, 100, 148);
const HOME_TARGET = new THREE.Vector3(0, 3, -19);
camera.position.copy(HOME_CAMERA);

const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
renderer.setSize(innerWidth, innerHeight);
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.02;
container.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.06;
controls.minDistance = 32;
controls.maxDistance = 240;
controls.maxPolarAngle = Math.PI * 0.47;
controls.target.copy(HOME_TARGET);

const hemi = new THREE.HemisphereLight(0xdff5ff, 0x526248, 1.15);
scene.add(hemi);
const sun = new THREE.DirectionalLight(0xfff3d6, 2.7);
sun.position.set(-60, 95, 42);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
sun.shadow.camera.left = -100;
sun.shadow.camera.right = 100;
sun.shadow.camera.top = 100;
sun.shadow.camera.bottom = -100;
sun.shadow.camera.far = 260;
sun.shadow.bias = -0.0005;
scene.add(sun);

const skyMaterial = new THREE.ShaderMaterial({
    side: THREE.BackSide,
    depthWrite: false,
    uniforms: {
        topColor: { value: new THREE.Color(0x54a8dc) },
        bottomColor: { value: new THREE.Color(0xeaf4ee) },
        offset: { value: 28 },
        exponent: { value: .72 },
    },
    vertexShader: "varying vec3 vWorldPosition; void main(){ vec4 worldPosition = modelMatrix * vec4(position, 1.0); vWorldPosition = worldPosition.xyz; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }",
    fragmentShader: "uniform vec3 topColor; uniform vec3 bottomColor; uniform float offset; uniform float exponent; varying vec3 vWorldPosition; void main(){ float h = normalize(vWorldPosition + vec3(0.0, offset, 0.0)).y; gl_FragColor = vec4(mix(bottomColor, topColor, max(pow(max(h, 0.0), exponent), 0.0)), 1.0); }",
});
scene.add(new THREE.Mesh(new THREE.SphereGeometry(550, 32, 18), skyMaterial));

const world = new THREE.Group();
scene.add(world);
const interactive = [];
const facilityMap = new Map();

function makeNoiseTexture(base, accent, repeatX = 8, repeatY = 8, lines = false) {
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = 256;
    const context = canvas.getContext("2d");
    context.fillStyle = base;
    context.fillRect(0, 0, 256, 256);
    context.globalAlpha = .18;
    for (let i = 0; i < 1450; i += 1) {
        context.fillStyle = i % 3 ? accent : "#ffffff";
        const size = 1 + (i * 13) % 3;
        context.fillRect((i * 47) % 256, (i * 83) % 256, size, size);
    }
    if (lines) {
        context.globalAlpha = .32;
        context.strokeStyle = accent;
        context.lineWidth = 1;
        for (let x = 0; x <= 256; x += 16) { context.beginPath(); context.moveTo(x, 0); context.lineTo(x, 256); context.stroke(); }
    }
    context.globalAlpha = 1;
    const texture = new THREE.CanvasTexture(canvas);
    texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
    texture.repeat.set(repeatX, repeatY);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.anisotropy = Math.min(renderer.capabilities.getMaxAnisotropy(), 8);
    return texture;
}

const groundTexture = makeNoiseTexture("#789168", "#496a43", 18, 18);
const concreteTexture = makeNoiseTexture("#aaa99d", "#6f736d", 14, 14);
const roadTexture = makeNoiseTexture("#505754", "#252c2a", 20, 20);
const wallTexture = makeNoiseTexture("#c2ae80", "#8f805f", 6, 5);
const roofTexture = makeNoiseTexture("#aebabe", "#68777a", 7, 7, true);
const redRoofTexture = makeNoiseTexture("#87463f", "#4f2926", 7, 7, true);

const MAT = {
    ground: new THREE.MeshStandardMaterial({ map: groundTexture, roughness: 1 }),
    concrete: new THREE.MeshStandardMaterial({ map: concreteTexture, roughness: .94 }),
    road: new THREE.MeshStandardMaterial({ map: roadTexture, roughness: 1 }),
    wall: new THREE.MeshStandardMaterial({ map: wallTexture, roughness: .76 }),
    wallLight: new THREE.MeshStandardMaterial({ color: 0xd1c79d, roughness: .8 }),
    roof: new THREE.MeshStandardMaterial({ map: roofTexture, metalness: .32, roughness: .58 }),
    roofBlue: new THREE.MeshStandardMaterial({ color: 0x6f8992, metalness: .35, roughness: .5 }),
    redRoof: new THREE.MeshStandardMaterial({ map: redRoofTexture, roughness: .7 }),
    glass: new THREE.MeshStandardMaterial({ color: 0x315a66, metalness: .12, roughness: .3 }),
    metal: new THREE.MeshStandardMaterial({ color: 0x79898b, metalness: .78, roughness: .32 }),
    tank: new THREE.MeshStandardMaterial({ color: 0xc5ccca, metalness: .6, roughness: .35 }),
    pipe: new THREE.MeshStandardMaterial({ color: 0x9b9a86, metalness: .62, roughness: .38 }),
    pipeDark: new THREE.MeshStandardMaterial({ color: 0x334044, metalness: .82, roughness: .27 }),
    pipeYellow: new THREE.MeshStandardMaterial({ color: 0xc79d39, metalness: .45, roughness: .46 }),
    frame: new THREE.MeshStandardMaterial({ color: 0x4c5556, metalness: .72, roughness: .38 }),
    concreteDark: new THREE.MeshStandardMaterial({ color: 0x747b75, roughness: .92 }),
    white: new THREE.MeshStandardMaterial({ color: 0xe1e4df, roughness: .7 }),
    greenhouse: new THREE.MeshPhysicalMaterial({ color: 0xd9e1d9, transparent: true, opacity: .62, roughness: .38, transmission: .08 }),
    trunk: new THREE.MeshStandardMaterial({ color: 0x5d4934, roughness: 1 }),
    foliage: new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 1 }),
};

function mesh(geometry, material, x = 0, y = 0, z = 0) {
    const object = new THREE.Mesh(geometry, material);
    object.position.set(x, y, z);
    object.castShadow = true;
    object.receiveShadow = true;
    world.add(object);
    return object;
}

function box(w, h, d, material, x, y, z) {
    return mesh(new THREE.BoxGeometry(w, h, d), material, x, y, z);
}

function cylinder(radius, height, material, x, y, z, radialSegments = 18) {
    return mesh(new THREE.CylinderGeometry(radius, radius, height, radialSegments), material, x, y, z);
}

function pipeBetween(start, end, radius = .16, material = MAT.pipe) {
    const direction = end.clone().sub(start);
    const pipeMesh = mesh(new THREE.CylinderGeometry(radius, radius, direction.length(), 10), material, 0, 0, 0);
    pipeMesh.position.copy(start).add(end).multiplyScalar(.5);
    pipeMesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction.clone().normalize());
    return pipeMesh;
}

function gableRoof(w, d, rise, material, x, y, z, rotationY = 0) {
    const shape = new THREE.Shape();
    shape.moveTo(-w / 2, 0);
    shape.lineTo(0, rise);
    shape.lineTo(w / 2, 0);
    shape.lineTo(-w / 2, 0);
    const geometry = new THREE.ExtrudeGeometry(shape, { depth: d, bevelEnabled: false });
    geometry.translate(0, 0, -d / 2);
    const roofMesh = mesh(geometry, material, x, y, z);
    roofMesh.rotation.y = rotationY;
    return roofMesh;
}

function roofVent(x, y, z, scale = 1) {
    cylinder(.48 * scale, .8 * scale, MAT.metal, x, y, z, 14);
    const cap = mesh(new THREE.ConeGeometry(.72 * scale, .35 * scale, 14), MAT.metal, x, y + .55 * scale, z);
    cap.rotation.y = Math.PI / 8;
}

function facadeWindows(x, z, w, h, d, rows, cols, direction = "front") {
    const group = new THREE.Group();
    const geometry = new THREE.PlaneGeometry(1.18, .74);
    const spanX = w - 3;
    const spanY = h - 2.4;
    for (let row = 0; row < rows; row += 1) {
        for (let col = 0; col < cols; col += 1) {
            const pane = new THREE.Mesh(geometry, MAT.glass);
            pane.position.set(-spanX / 2 + spanX * col / Math.max(cols - 1, 1), 1.25 + spanY * row / Math.max(rows - 1, 1), 0);
            group.add(pane);
        }
    }
    if (direction === "front") group.position.set(x, 0, z + d / 2 + .02);
    if (direction === "back") { group.position.set(x, 0, z - d / 2 - .02); group.rotation.y = Math.PI; }
    world.add(group);
    return group;
}

function register(object, data) {
    object.userData.facility = data;
    interactive.push(object);
    if (!facilityMap.has(data.key)) facilityMap.set(data.key, { object, data });
    return object;
}

function addWindows(building, width, height, depth, rows, cols, side = "front") {
    const geometry = new THREE.PlaneGeometry(1.25, .72);
    const windows = new THREE.Group();
    const spanX = width - 3;
    const spanY = height - 2.3;
    for (let row = 0; row < rows; row += 1) {
        for (let col = 0; col < cols; col += 1) {
            const windowMesh = new THREE.Mesh(geometry, MAT.glass);
            windowMesh.position.set(
                -spanX / 2 + (spanX / Math.max(cols - 1, 1)) * col,
                -spanY / 2 + (spanY / Math.max(rows - 1, 1)) * row,
                depth / 2 + .012
            );
            windows.add(windowMesh);
        }
    }
    if (side === "back") windows.rotation.y = Math.PI;
    building.add(windows);
}

function factoryBuilding({ key, title, description, load, index, x, z, w, h, d, roof = MAT.roof, wall = MAT.wall, rows = 3, cols = 7 }) {
    const building = new THREE.Group();
    building.position.set(x, 0, z);
    world.add(building);
    const body = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), wall);
    body.position.y = h / 2;
    body.castShadow = body.receiveShadow = true;
    building.add(body);
    const roofMesh = new THREE.Mesh(new THREE.BoxGeometry(w + .7, .55, d + .7), roof);
    roofMesh.position.y = h + .28;
    roofMesh.castShadow = true;
    building.add(roofMesh);
    addWindows(body, w, h, d, rows, cols);
    const data = { key, title, description, load, index };
    register(body, data);
    return building;
}

// Layout inferred from the supplied aerial photograph; dimensions are approximate.
const ground = mesh(new THREE.PlaneGeometry(1800, 1800), MAT.ground, 0, -.2, 0);
ground.rotation.x = -Math.PI / 2;
function paving(x,z,w,d, material=MAT.concrete) {
    const p=mesh(new THREE.PlaneGeometry(w,d),material,x,-.04,z);
    p.rotation.x=-Math.PI/2;
}
paving(0,0,145,145);
paving(-12,57,155,5); paving(-64,-15,5,145); paving(6,27,8,83);

// Mullioned industrial glazing on all four elevations, with floor bands.
function detailedBlock(key,title,index,x,z,w,h,d,rows,cols,roof=MAT.roof) {
    const building=factoryBuilding({key,title,index,description:"Surat asosida taxminan tiklangan bino.",load:"Demo",x,z,w,h,d,rows:0,cols:0,roof});
    const body=building.children[0];
    const windowMat=MAT.glass;
    for(let side=0;side<4;side++) {
        const face=new THREE.Group();
        const span=side%2?d:w, n=side%2?Math.max(3,Math.round(cols*d/w)):cols;
        face.rotation.y=side*Math.PI/2;
        for(let row=0;row<rows;row++) for(let col=0;col<n;col++) {
            const ww=(span-3)/n*.49, wh=Math.min(2.05,h/rows*.62);
            const wx=-span/2+1.5+(col+.5)*(span-3)/n;
            const wy=1.5+(row+.5)*(h-2)/rows;
            const pane=new THREE.Mesh(new THREE.PlaneGeometry(ww,wh),windowMat);
            pane.position.set(wx,wy, (side%2?w:d)/2+.03); face.add(pane);
            for(const [bw,bh,dx,dy] of [[.055,wh,0,0],[ww,.055,0,0],[ww,.05,0,wh/2]]) {
                const bar=new THREE.Mesh(new THREE.BoxGeometry(bw,bh,.055),MAT.white);
                bar.position.set(wx+dx,wy+dy,(side%2?w:d)/2+.065); face.add(bar);
            }
        }
        building.add(face);
    }
    for(let row=1;row<rows;row++) {
        const band=new THREE.Mesh(new THREE.BoxGeometry(w+.06,.16,d+.06),MAT.wallLight);
        band.position.y=row*h/rows; building.add(band);
    }
    // Standing seams across the low-pitched metal roof.
    for(let xx=-w/2;xx<w/2;xx+=2.4) {
        const seam=new THREE.Mesh(new THREE.BoxGeometry(.055,.08,d+.55),MAT.metal);
        seam.position.set(xx,h+.61,0);building.add(seam);
    }
    return body;
}
detailedBlock("Main production","Asosiy ishlab chiqarish","01",-27,20,42,19,25,5,11);
// The right-hand section has continuous glazed bands in the reference.
for(let y=3;y<19;y+=3.5) {
    box(12,1.9,.12,MAT.glass,-13,y,32.6);
    for(let x=-19;x<=-7;x+=.75)box(.055,1.9,.16,MAT.white,x,y,32.7);
    box(12,.06,.16,MAT.white,-13,y,32.7);
}
detailedBlock("Processing block","Qayta ishlash sexi","02",30,-3,29,24,29,6,9);

// Broad left-hand sheds recede into the photograph, parallel to the rail siding.
detailedBlock("Warehouse","Ombor majmuasi","04",-62,-29,21,6,74,1,5);
gableRoof(22,75,1.7,MAT.roof,-62,6.35,-29);
for(let z=-63;z<10;z+=12)box(22,.17,.18,MAT.metal,-62,6.5,z);
detailedBlock("Utility hall","Texnik korpus","06",-33,-56,11,10,11,3,3);
// Long blue-edged rear hall, aligned toward the distant chimney.
detailedBlock("Utility hall","Uzun ishlab chiqarish liniyasi","06",8,-47,13,7,64,2,4);
gableRoof(14,65,2,MAT.roof,8,7.4,-47);
box(1.2,.5,65,MAT.roofBlue,1,7.5,-47);
box(1.2,.5,65,MAT.roofBlue,15,7.5,-47);
detailedBlock("Utility hall","Elevator minorasi","06",10,-62,8,16,8,3,3);
detailedBlock("Utility hall","Orqa korpus","06",-28,-91,22,10,9,3,7);

// Foreground red-roofed U-shaped administration block and its planted courtyard.
detailedBlock("Office","Ma’muriy bino","05",40,52,40,10,12,3,13,MAT.redRoof);
gableRoof(12.7,41,2.5,MAT.redRoof,40,10.4,52,Math.PI/2);
for(const x of [24,56]) {
    detailedBlock("Office","Ma’muriy qanot","05",x,36,8,10,21,3,3,MAT.redRoof);
    gableRoof(8.7,22,2.2,MAT.redRoof,x,10.4,36);
}
paving(40,36,22,19,MAT.ground);
box(8,.4,4,MAT.concrete,40,.2,61);
gableRoof(7,4,1.1,MAT.redRoof,40,4,60);
for(const x of [37,43])box(.22,4,.22,MAT.wallLight,x,2,61);

// Two rows of flat-top tanks BEHIND the foreground production building.
const tankData={key:"Tank farm",title:"Rezervuarlar",index:"03",description:"Suratdagi ikki qator silindrsimon rezervuar.",load:"Demo"};
for(let row=0;row<4;row++)for(let col=0;col<2;col++) {
    const x=-19+col*7,z=-9-row*7,h=7.5+(row%2)*1.3;
    register(cylinder(2.55,h,MAT.tank,x,h/2,z,32),tankData);
    cylinder(2.6,.17,MAT.roof,x,h+.085,z,32);
    cylinder(.4,.3,MAT.metal,x+.8,h+.2,z);
    for(let y=1.8;y<h;y+=2) {
        const ring=mesh(new THREE.TorusGeometry(2.56,.035,5,32),MAT.metal,x,y,z);ring.rotation.x=Math.PI/2;
    }
    for(const dx of [2.62,3.12])pipeBetween(new THREE.Vector3(x+dx,.1,z),new THREE.Vector3(x+dx,h+.6,z),.045,MAT.frame);
    for(let y=.4;y<h+.6;y+=.5)pipeBetween(new THREE.Vector3(x+2.62,y,z),new THREE.Vector3(x+3.12,y,z),.035,MAT.frame);
}

// Open six-level steel process structure sits between the two major blocks.
for(const x of [1,7,13])for(const z of [-5,3,11])box(.28,21,.28,MAT.frame,x,10.5,z);
for(let y=3;y<=21;y+=3.5) {
    for(const z of [-5,3,11])box(12.4,.23,.28,MAT.frame,7,y,z);
    for(const x of [1,7,13])box(.28,.23,16.3,MAT.frame,x,y,3);
    for(const x of [1,13]) {
        pipeBetween(new THREE.Vector3(x,y-3.5,-5),new THREE.Vector3(x,y,3),.09,MAT.frame);
        pipeBetween(new THREE.Vector3(x,y-3.5,3),new THREE.Vector3(x,y,11),.09,MAT.frame);
    }
    cylinder(1.35,2.7,MAT.tank,5,y-1.4,0);
    cylinder(.9,2.8,MAT.pipeDark,10,y-1.4,7);
}
box(13,.3,17,MAT.roof,7,21.3,3);
for(const x of [2,5,8,11]) {
    pipeBetween(new THREE.Vector3(x,1,13),new THREE.Vector3(x,18,13),.15,MAT.pipe);
    pipeBetween(new THREE.Vector3(x,18,13),new THREE.Vector3(16,18,13),.15,MAT.pipe);
}
cylinder(4,2.3,MAT.tank,3,1.15,18,40);
const rail=mesh(new THREE.TorusGeometry(4.05,.075,6,40),MAT.pipeYellow,3,3.2,18);rail.rotation.x=Math.PI/2;
for(let i=0;i<16;i++){const a=i*Math.PI/8;box(.06,1.1,.06,MAT.metal,3+4*Math.cos(a),2.7,18+4*Math.sin(a));}

// Layered monitor roofs and vertical exterior duct on the taller block.
box(24,2.4,13,MAT.frame,30,25.6,-3);
box(25,.32,14,MAT.roof,30,27,-3);
for(let x=19;x<=41;x+=3)box(.2,2.4,.2,MAT.white,x,25.6,3.5);
box(17,1.7,7,MAT.wallLight,28,28,-6);
box(18,.3,8,MAT.roof,28,29,-6);
cylinder(.9,23,MAT.tank,15,11.5,10);
for(let y=2;y<23;y+=2)box(1.9,.1,1.9,MAT.metal,15,y,10);
box(5,1.6,4,MAT.wallLight,-23,20.3,17);
box(5.6,.2,4.6,MAT.roof,-23,21.2,17);

// Pipe bridge across rear service yard and rail siding.
for(const z of [-42,-40,-38]) {
    pipeBetween(new THREE.Vector3(-49,8,z),new THREE.Vector3(2,8,z),.13,MAT.pipeDark);
    for(let x=-49;x<=2;x+=8)box(.17,8,.17,MAT.frame,x,4,z);
}
for(const x of [-43,-41,-37,-35])box(.09,.09,100,MAT.metal,x,.03,-26);
for(let z=-75;z<25;z+=1.5)box(10,.1,.25,MAT.concreteDark,-39,-.015,z);
gableRoof(7,13,2,MAT.roof,-40,5,-22);
for(const x of [-43,-37])for(const z of [-28,-16])box(.2,5,.2,MAT.frame,x,2.5,z);

// Low white covered stores to the right of the process block.
for(let i=0;i<5;i++) {
    const arch=mesh(new THREE.CylinderGeometry(2.3,2.3,32,24,1,true,0,Math.PI),MAT.white,60,-.02,-18+i*5.2);
    arch.rotation.z=Math.PI/2;
}
detailedBlock("Utility hall","Qozonxona","06",69,22,19,5,11,1,5,MAT.redRoof);
gableRoof(12,20,1.4,MAT.redRoof,69,5.3,22,Math.PI/2);
for(const x of [66,71])cylinder(.35,20,MAT.pipeDark,x,10,21);
const chimney=mesh(new THREE.CylinderGeometry(.45,1,35,24),new THREE.MeshStandardMaterial({color:0x78534b}),-27,17.5,-100);
register(chimney,{key:"Chimney",title:"Tutun minorasi",index:"07",description:"Orqa korpus yonidagi mo‘ri.",load:"Demo"});

// Seeded deciduous canopies, rather than evenly spaced toy conifers.
let seed=72;
function random(){seed=(1664525*seed+1013904223)>>>0;return seed/4294967296;}
const treePositions=[];
for(const [x,z,w,d] of [[-31,51,38,16],[-58,32,9,25],[-34,-25,12,20],[6,63,13,20]]) {
    paving(x,z,w,d,MAT.ground);
    for(let i=0;i<22;i++)treePositions.push([x+(random()-.5)*w,z+(random()-.5)*d]);
}
for(let i=0;i<155;i++) {
    const x=-76+random()*155,z=65+random()*29;
    if(Math.abs(x-7)>5 && !(x>17&&x<64&&z<70))treePositions.push([x,z]);
}
for(let i=0;i<120;i++)treePositions.push([-85+random()*9,-95+random()*160]);
for(let row=0;row<7;row++)for(let i=0;i<36;i++)treePositions.push([-90+i*6+random()*2,-115-row*13+random()*2]);
for(let i=0;i<30;i++)treePositions.push([35+random()*12,28+random()*14]);
const trunks=new THREE.InstancedMesh(new THREE.CylinderGeometry(.18,.3,2.8,6),MAT.trunk,treePositions.length);
const crowns=new THREE.InstancedMesh(new THREE.IcosahedronGeometry(1,1),MAT.foliage,treePositions.length*3);
const dummy=new THREE.Object3D();
treePositions.forEach(([x,z],i)=>{
    const size=1.4+random()*1.5;
    dummy.position.set(x,1.4,z);dummy.scale.set(1,1,1);dummy.updateMatrix();trunks.setMatrixAt(i,dummy.matrix);
    for(let j=0;j<3;j++){
        dummy.position.set(x+(random()-.5)*2,2.6+size*.5+j*.45,z+(random()-.5)*2);
        dummy.scale.set(size,size*.85,size);dummy.rotation.set(random(),random()*6,random());dummy.updateMatrix();
        crowns.setMatrixAt(i*3+j,dummy.matrix);
        crowns.setColorAt(i*3+j,new THREE.Color().setHSL(.24+random()*.08,.38+random()*.2,.15+random()*.12));
    }
});
crowns.castShadow=trunks.castShadow=true;world.add(trunks,crowns);
for(let i=0;i<24;i++) {
    const m=new THREE.MeshStandardMaterial({color:new THREE.Color().setHSL(.2+random()*.08,.25,.28+random()*.13)});
    paving(-290+(i%8)*80,-190-Math.floor(i/8)*90,72,82,m);
}
for(let i=0;i<28;i++) {
    const x=-220+random()*440,z=-260-random()*250,w=8+random()*24,d=5+random()*15;
    box(w,3,d,MAT.wallLight,x,1.5,z);gableRoof(w+.4,d+.4,1,MAT.roof,x,3,z);
}

const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
let hovered = null;

function setEmissive(object, active) {
    if (!object?.material?.emissive) return;
    if (!object.userData.highlightMaterial) {
        object.material = object.material.clone();
        object.userData.highlightMaterial = true;
    }
    object.material.emissive.set(active ? 0x21583f : 0x000000);
    object.material.emissiveIntensity = active ? .48 : 0;
}

function pick(event, open = false) {
    pointer.x = (event.clientX / innerWidth) * 2 - 1;
    pointer.y = -(event.clientY / innerHeight) * 2 + 1;
    raycaster.setFromCamera(pointer, camera);
    const hit = raycaster.intersectObjects(interactive, false)[0]?.object ?? null;
    if (hit !== hovered) {
        setEmissive(hovered, false);
        hovered = hit;
        setEmissive(hovered, true);
        renderer.domElement.style.cursor = hit ? "pointer" : "grab";
    }
    if (open && hit) showFacility(hit.userData.facility);
}

function showFacility(data) {
    document.querySelector("#info-index").textContent = `OBYEKT ${data.index}`;
    document.querySelector("#info-title").textContent = data.title;
    document.querySelector("#info-description").textContent = data.description;
    document.querySelector("#info-load").textContent = data.load;
    document.querySelector("#info-card").classList.add("is-visible");
    document.querySelectorAll("#facility-list button").forEach((button) => button.classList.toggle("is-active", button.dataset.target === data.key));
}

function focusFacility(key) {
    const entry = facilityMap.get(key);
    if (!entry) return;
    const target = new THREE.Vector3();
    entry.object.getWorldPosition(target);
    const direction = camera.position.clone().sub(controls.target).normalize();
    controls.target.copy(target);
    const focusDistance = innerWidth <= 760 ? 70 : 48;
    camera.position.copy(target.clone().add(direction.multiplyScalar(focusDistance)).add(new THREE.Vector3(0, innerWidth <= 760 ? 26 : 18, 0)));
    showFacility(entry.data);
    if (innerWidth <= 760) panel.classList.add("is-hidden");
}

renderer.domElement.addEventListener("pointermove", (event) => pick(event));
renderer.domElement.addEventListener("click", (event) => pick(event, true));
document.querySelectorAll("#facility-list button").forEach((button) => button.addEventListener("click", () => focusFacility(button.dataset.target)));

const panel = document.querySelector(".facility-panel");
panel.classList.add("is-hidden");
document.querySelector("#close-panel").addEventListener("click", () => panel.classList.add("is-hidden"));
document.querySelector("#toggle-panel").addEventListener("click", () => panel.classList.toggle("is-hidden"));
document.querySelector("#close-info").addEventListener("click", () => document.querySelector("#info-card").classList.remove("is-visible"));

const rotateButton = document.querySelector("#toggle-rotate");
rotateButton.addEventListener("click", () => {
    controls.autoRotate = !controls.autoRotate;
    controls.autoRotateSpeed = .45;
    rotateButton.classList.toggle("is-active", controls.autoRotate);
});

const photoButton = document.querySelector("#toggle-photo");
const photoReference = document.querySelector("#photo-reference");
photoButton.addEventListener("click", () => {
    const isVisible = photoReference.classList.toggle("is-visible");
    photoButton.classList.toggle("is-active", isVisible);
});

let isNight = false;
const dayButton = document.querySelector("#toggle-day");
dayButton.addEventListener("click", () => {
    isNight = !isNight;
    scene.background.set(isNight ? 0x08151f : 0x9bcbe3);
    scene.fog.color.set(isNight ? 0x14252b : 0xb9d4dc);
    hemi.intensity = isNight ? .5 : 1.15;
    sun.intensity = isNight ? .32 : 2.7;
    skyMaterial.uniforms.topColor.value.set(isNight ? 0x05111f : 0x54a8dc);
    skyMaterial.uniforms.bottomColor.value.set(isNight ? 0x172733 : 0xeaf4ee);
    renderer.toneMappingExposure = isNight ? .64 : 1.02;
    dayButton.textContent = isNight ? "☾" : "☼";
    dayButton.insertAdjacentHTML("beforeend", "<span>Yoritish</span>");
    dayButton.classList.toggle("is-active", isNight);
});

function resetCamera() {
    const distanceScale = innerWidth <= 760 ? 1.35 : innerWidth <= 1100 ? 1.12 : 1;
    const homeOffset = HOME_CAMERA.clone().sub(HOME_TARGET).multiplyScalar(distanceScale);
    camera.position.copy(HOME_TARGET).add(homeOffset);
    controls.target.copy(HOME_TARGET);
    camera.fov = innerWidth <= 760 ? 50 : 42;
    camera.updateProjectionMatrix();
    controls.update();
}
resetCamera();
document.querySelector("#reset-camera").addEventListener("click", resetCamera);

addEventListener("resize", () => {
    camera.aspect = innerWidth / innerHeight;
    camera.fov = innerWidth <= 760 ? 50 : 42;
    camera.updateProjectionMatrix();
    renderer.setSize(innerWidth, innerHeight);
});

let elapsed = 0;
const clock = new THREE.Clock();
function animate() {
    requestAnimationFrame(animate);
    elapsed += clock.getDelta();
    controls.update();
    renderer.render(scene, camera);
}
animate();

requestAnimationFrame(() => {
    setTimeout(() => document.querySelector("#loading-screen").classList.add("is-hidden"), 450);
    setTimeout(() => document.querySelector("#scene-hint").classList.add("is-hidden"), 6500);
});
