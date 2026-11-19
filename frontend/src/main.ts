import { bootstrapApplication } from '@angular/platform-browser';
import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpClient, provideHttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { firstValueFrom } from 'rxjs';
import { provideRouter, RouterLink, RouterOutlet, Routes } from '@angular/router';

interface Activity { id:string; name:string; }
interface AIResponse { mode: string; provider: string; result: string; promptUsed: string; }
@Component({selector:'app-alumno',standalone:true,imports:[FormsModule,CommonModule],template:`
<section class="card"><h2>👩‍🎓 Generador de trabajos — Alumno</h2><p>Compara un prompt general con otro que incluye contexto académico.</p>
<label>Tema</label><input [(ngModel)]="topic" maxlength="300" placeholder="Ej. El ciclo del agua">
<label>Actividad</label><select [(ngModel)]="activity"><option *ngFor="let item of activities" [value]="item.id">{{item.name}}</option></select>
<label *ngIf="activity==='personalizada'">Describe la tarea personalizada</label><textarea *ngIf="activity==='personalizada'" [(ngModel)]="customInstructions" maxlength="4000" rows="4" placeholder="Ej. Crea un mapa conceptual..." ></textarea>
<label>Material de apoyo (opcional)</label><textarea [(ngModel)]="sourceText" maxlength="12000" rows="5" placeholder="Pega aquí tus apuntes..."></textarea>
<div class="actions"><button (click)="generate('simple')" [disabled]="loading || !topic.trim()">Sin contexto</button><button class="primary" (click)="generate('context')" [disabled]="loading || !topic.trim()">Con contexto</button><button class="outline" (click)="compare()" [disabled]="loading || !topic.trim()">Comparar ambos</button></div>
<p *ngIf="loading">Procesando…</p><p class="error" *ngIf="error">{{error}}</p></section>
<section class="grid"><article class="card result"><h2>Sin contexto</h2><span class="badge" *ngIf="simple">{{simple.provider}}</span><pre>{{simple?.result || 'Sin resultado todavía'}}</pre><details *ngIf="simple"><summary>Ver prompt</summary><pre>{{simple.promptUsed}}</pre></details></article><article class="card result"><h2>Con contexto</h2><span class="badge" *ngIf="context">{{context.provider}}</span><pre>{{context?.result || 'Sin resultado todavía'}}</pre><details *ngIf="context"><summary>Ver prompt</summary><pre>{{context.promptUsed}}</pre></details></article></section>`})
class AlumnoComponent {
 private http=inject(HttpClient); topic='El ciclo del agua'; workType='summary'; sourceText=''; activity='resumen';customInstructions='';activities:Activity[]=[];
 async ngOnInit(){try{this.activities=await firstValueFrom(this.http.get<Activity[]>('/api/activities/alumno'));}catch{this.error='No se pudieron cargar las actividades';}}
 simple?:AIResponse;context?:AIResponse;loading=false;error='';
 async generate(mode:'simple'|'context') {this.loading=true;this.error='';try {const r=await firstValueFrom(this.http.post<AIResponse>('/api/study/generate',{topic:this.topic,workType:this.workType,sourceText:this.sourceText,activity:this.activity,customInstructions:this.customInstructions,mode}));if(mode==='simple')this.simple=r;else this.context=r;}catch(e:any){this.error=e?.error?.error||'No se pudo conectar con la API.';}finally{this.loading=false;}}
 async compare(){await this.generate('simple');await this.generate('context');}
}
@Component({selector:'app-docente',standalone:true,imports:[FormsModule,CommonModule],template:`
<section class="card"><h2>👨‍🏫 Evaluador de resúmenes — Docente</h2><p>La IA propone una evaluación, pero la decisión final es del docente.</p>
<label>Tema del resumen</label><input [(ngModel)]="topic" maxlength="300" placeholder="Ej. Arquitectura de software">
<label>Actividad docente</label><select [(ngModel)]="activity"><option *ngFor="let item of activities" [value]="item.id">{{item.name}}</option></select>
<label *ngIf="activity==='personalizada'">Describe la tarea personalizada</label><textarea *ngIf="activity==='personalizada'" [(ngModel)]="customInstructions" maxlength="4000" rows="4" placeholder="Ej. Identifica errores conceptuales..." ></textarea>
<label>Instrucciones originales del trabajo (opcional)</label><textarea [(ngModel)]="instructions" maxlength="3000" rows="3" placeholder="Ej. Explicar componentes y agregar un ejemplo..."></textarea>
<label>Resumen entregado por el alumno</label><textarea [(ngModel)]="studentText" maxlength="12000" rows="8" placeholder="Pega el resumen que se evaluará..."></textarea>
<div class="actions"><button (click)="generate('simple')" [disabled]="loading || !topic.trim() || !studentText.trim()">Evaluar sin contexto</button><button class="primary" (click)="generate('context')" [disabled]="loading || !topic.trim() || !studentText.trim()">Evaluar con rúbrica</button><button class="outline" (click)="compare()" [disabled]="loading || !topic.trim() || !studentText.trim()">Comparar evaluaciones</button></div>
<p *ngIf="loading">Evaluando…</p><p class="error" *ngIf="error">{{error}}</p></section>
<section class="grid"><article class="card result"><h2>Sin contexto</h2><span class="badge" *ngIf="simple">{{simple.provider}}</span><pre>{{simple?.result || 'Sin evaluación todavía'}}</pre><details *ngIf="simple"><summary>Ver prompt</summary><pre>{{simple.promptUsed}}</pre></details></article><article class="card result"><h2>Con contexto y rúbrica</h2><span class="badge" *ngIf="context">{{context.provider}}</span><pre>{{context?.result || 'Sin evaluación todavía'}}</pre><details *ngIf="context"><summary>Ver prompt</summary><pre>{{context.promptUsed}}</pre></details></article></section>
<p class="notice">⚠️ Las calificaciones de IA son sugerencias formativas. No son decisiones automáticas ni pruebas de autoría. Usa textos ficticios o anonimizados.</p>`})
class DocenteComponent {
 private http=inject(HttpClient);activity='evaluacion-resumen';customInstructions='';activities:Activity[]=[];
 async ngOnInit(){try{this.activities=await firstValueFrom(this.http.get<Activity[]>('/api/activities/docente'));}catch{this.error='No se pudieron cargar las actividades';}}
 topic='Arquitectura de software';studentText='La arquitectura de software organiza los componentes de un sistema y define cómo se comunican. Ayuda a mantener el código y mejorar su escalabilidad.';instructions='';
 simple?:AIResponse;context?:AIResponse;loading=false;error='';
 async generate(mode:'simple'|'context') {this.loading=true;this.error='';try {const r=await firstValueFrom(this.http.post<AIResponse>('/api/grade/evaluate',{topic:this.topic,studentText:this.studentText,instructions:this.instructions,activity:this.activity,customInstructions:this.customInstructions,mode}));if(mode==='simple')this.simple=r;else this.context=r;}catch(e:any){this.error=e?.error?.error||'No se pudo conectar con la API.';}finally{this.loading=false;}}
 async compare(){await this.generate('simple');await this.generate('context');}
}

@Component({selector:'app-incidentes',standalone:true,imports:[FormsModule,CommonModule],template:`
<section class="card"><h2>🛠️ SmartApps · Clasificador de incidentes</h2><p>Compara una clasificación general con otra guiada por categorías, impacto y urgencia. No crea tickets reales.</p>
<label>Descripción del incidente</label><textarea [(ngModel)]="description" maxlength="6000" rows="7" placeholder="Ej. El servicio VPN no funciona para 20 colaboradores desde las 8:00..." ></textarea>
<div class="actions"><button (click)="classify('simple')" [disabled]="loading || description.trim().length<5">Sin contexto</button><button class="primary" (click)="classify('context')" [disabled]="loading || description.trim().length<5">Con contexto</button><button class="outline" (click)="compare()" [disabled]="loading || description.trim().length<5">Comparar ambos</button></div>
<p *ngIf="loading">Clasificando…</p><p class="error" *ngIf="error">{{error}}</p></section>
<section class="grid"><article class="card result"><h2>Sin contexto</h2><span class="badge" *ngIf="simple">{{simple.provider}}</span><pre>{{simple?.result || 'Sin resultado todavía'}}</pre><details *ngIf="simple"><summary>Ver prompt</summary><pre>{{simple.promptUsed}}</pre></details></article><article class="card result"><h2>Con contexto</h2><span class="badge" *ngIf="context">{{context.provider}}</span><pre>{{context?.result || 'Sin resultado todavía'}}</pre><details *ngIf="context"><summary>Ver prompt</summary><pre>{{context.promptUsed}}</pre></details></article></section>
<p class="notice">⚠️ Modo demostración: usa reglas de palabras clave, no inteligencia artificial. Con Gemini las respuestas son sugerencias y requieren validación humana. No introduzcas contraseñas ni datos personales.</p>`})
class IncidentesComponent {
 private http=inject(HttpClient); description='No funciona la VPN para 20 colaboradores desde las 8:00. No pueden acceder al sistema de trabajo.';
 simple?:AIResponse;context?:AIResponse;loading=false;error='';
 async classify(mode:'simple'|'context') {this.loading=true;this.error='';try {const r=await firstValueFrom(this.http.post<AIResponse>('/api/incidents/classify',{description:this.description,mode}));if(mode==='simple')this.simple=r;else this.context=r;}catch(e:any){this.error=e?.error?.detail||'No se pudo conectar con la API.';}finally{this.loading=false;}}
 async compare(){await this.classify('simple');await this.classify('context');}
}
@Component({selector:'app-root',standalone:true,imports:[RouterLink,RouterOutlet],template:`<main class="wrap"><header><span class="eyebrow">JORNADA ACADÉMICA · IA + CONTEXT ENGINEERING</span><h1>SmartEdu <em>AI</em></h1><p>Tres módulos para aprender cómo el contexto transforma las respuestas de IA.</p><nav><a routerLink="/alumno">🎓 Alumno · /alumno</a><a routerLink="/docente">📋 Docente · /docente</a><a routerLink="/incidentes">🛠️ SmartApps · /incidentes</a></nav></header><router-outlet></router-outlet><footer>Sin GEMINI_API_KEY se muestran ejemplos simulados, no resultados reales de IA.</footer></main>`})
class AppComponent {}
const routes: Routes=[{path:'alumno',component:AlumnoComponent},{path:'docente',component:DocenteComponent},{path:'incidentes',component:IncidentesComponent},{path:'',pathMatch:'full',redirectTo:'alumno'},{path:'**',redirectTo:'alumno'}];
bootstrapApplication(AppComponent,{providers:[provideHttpClient(),provideRouter(routes)]}).catch(console.error);
