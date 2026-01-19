

pipeline {
  agent any

    tools {
  git 'Default'
  }

  environment {
    IMAGE_REPO = "katiravan/mldevops"    
    NAMESPACE  = "mldevopskatir"          
    APP_NAME   = "mldevops"            
    SERVICE    = "mldevops"             
  }

  options { timestamps() }

  stages {

    stage('Checkout') {
      steps {
        checkout scm
        bat 'git --version'
        bat 'docker --version'
        bat 'kubectl version --client=true'
        bat 'git status'
        bat 'git rev-parse HEAD'
      }
    }

   stage('Compute Tags') {
  steps {
    script {
      env.SHORTSHA = bat(returnStdout: true, script: '@echo off\r\ngit rev-parse --short=7 HEAD').trim()

      def s = bat(returnStatus: true, script: '@echo off\r\ngit describe --tags --exact-match 1> .reltag.txt 2>nul')
      env.RELTAG = (s == 0) ? readFile('.reltag.txt').trim() : ''
    }
    bat '@echo on\necho SHORTSHA=%SHORTSHA%\necho RELTAG=%RELTAG%'
  }
}

    stage('QA (Unit Tests)') {
      steps {
        bat '''
          @echo on
          python --version
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest

          if not exist reports mkdir reports
          python -m pytest -q --junitxml=reports\\test-results.xml
          dir reports
        '''
      }
      post {
        always {
          junit 'reports/test-results.xml'
          archiveArtifacts artifacts: 'reports/test-results.xml', fingerprint: true
        }
      }
    }

   stage('Build Image') {
  steps {
    script {
      if (!(env.SHORTSHA ==~ /^[0-9a-f]{7}$/)) {
        error("SHORTSHA invalid. Expected 7-hex, got: '${env.SHORTSHA}'")
      }
      if (env.RELTAG && !(env.RELTAG ==~ /^[0-9A-Za-z._-]+$/)) {
        error("RELTAG invalid. Got: '${env.RELTAG}'")
      }
    }

    bat '''
      @echo on
      echo Building image: "%IMAGE_REPO%:git-%SHORTSHA%"
      docker build -t "%IMAGE_REPO%:git-%SHORTSHA%" .

      if not "%RELTAG%"=="" (
        echo Applying release tag: %RELTAG%
        docker tag "%IMAGE_REPO%:git-%SHORTSHA%" "%IMAGE_REPO%:%RELTAG%"
      ) else (
        echo No release tag. Skipping SemVer tag.
      )
    '''
  }
}

    stage('Push Image') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'registry-creds', usernameVariable: 'DOCKER_USER', passwordVariable: 'DOCKER_PASS')]) {
          bat '''
            @echo on
            echo %DOCKER_PASS% | docker login -u %DOCKER_USER% --password-stdin

            docker push %IMAGE_REPO%:git-%SHORTSHA%

            if not "%RELTAG%"=="" (
              docker push %IMAGE_REPO%:%RELTAG%
            ) else (
              echo No release tag. Skipping push for SemVer tag.
            )
          '''
        }
      }
    }

    stage('Deploy to Kubernetes (Apply + Set Image)') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG_FILE')]) {
          bat '''
            @echo on
            set KUBECONFIG=%KUBECONFIG_FILE%

            kubectl apply -f k8s\\namespace.yaml
            kubectl apply -f k8s\\deployment.yaml
            kubectl apply -f k8s\\service.yaml

            echo Setting image to: %IMAGE_REPO%:git-%SHORTSHA%
            kubectl -n %NAMESPACE% set image deployment/%APP_NAME% %APP_NAME%=%IMAGE_REPO%:git-%SHORTSHA%
          '''
        }
      }
    }

    stage('Rollout Gate (Must Succeed)') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG_FILE')]) {
          bat '''
            @echo on
            set KUBECONFIG=%KUBECONFIG_FILE%

            kubectl -n %NAMESPACE% rollout status deployment/%APP_NAME% --timeout=180s
            kubectl -n %NAMESPACE% get pods -o wide
            kubectl -n %NAMESPACE% get svc
          '''
        }
      }
    }

    stage('Smoke Test (/health)') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG_FILE')]) {
          bat '''
            @echo on
            set KUBECONFIG=%KUBECONFIG_FILE%
            
            set POD=curl-%BUILD_NUMBER%
            
            echo ===== cleanup any old curl pods =====
              kubectl -n %NAMESPACE% delete pod curl --ignore-not-found
              kubectl -n %NAMESPACE% delete pod %POD% --ignore-not-found
    
            echo ===== smoke test /health =====
            kubectl -n %NAMESPACE% run %POD% --rm -i --restart=Never --image=curlimages/curl -- ^
              curl -sS http://%SERVICE%:8000/health || exit /b 1
              '''
        }
      }
    }

stage('Load Test (k6)') {
  steps {
    withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG_FILE')]) {
      bat '''
        setlocal EnableExtensions EnableDelayedExpansion
        set "KUBECONFIG=%KUBECONFIG_FILE%"
        set "NS=mldevopskatir"
        set "JOB=k6"
        set "CM=k6-script"
        set "SCRIPT=loadtest\\k6.js"
        set "BASE_URL=http://mldevops:8000"

        echo ===== Validate k6 script exists =====
        if not exist "%SCRIPT%" (
          echo ERROR: k6 script not found: %CD%\\%SCRIPT%
          dir /s loadtest
          exit /b 1
        )

        echo ===== Cleanup old k6 resources =====
        kubectl -n %NS% delete job %JOB% --ignore-not-found
        kubectl -n %NS% delete configmap %CM% --ignore-not-found

        echo ===== Create configmap from script =====
        kubectl -n %NS% create configmap %CM% --from-file=k6.js="%SCRIPT%"
        if errorlevel 1 exit /b 1

        echo ===== Write job manifest =====
        > k6-job.yaml (
          echo apiVersion: batch/v1
          echo kind: Job
          echo metadata:
          echo   name: %JOB%
          echo   namespace: %NS%
          echo spec:
          echo   backoffLimit: 0
          echo   template:
          echo     metadata:
          echo       labels:
          echo         app: k6
          echo     spec:
          echo       restartPolicy: Never
          echo       containers:
          echo       - name: k6
          echo         image: grafana/k6:0.51.0
          echo         imagePullPolicy: IfNotPresent
          echo         env:
          echo         - name: BASE_URL
          echo           value: "%BASE_URL%"
          echo         volumeMounts:
          echo         - name: script
          echo           mountPath: /scripts
          echo         command: ["k6","run","/scripts/k6.js"]
          echo       volumes:
          echo       - name: script
          echo         configMap:
          echo           name: %CM%
        )

        echo ===== Apply job =====
        kubectl apply -f k6-job.yaml
        if errorlevel 1 exit /b 1

        echo ===== Wait for job to finish (complete or failed) =====
        kubectl -n %NS% wait --for=condition=complete job/%JOB% --timeout=6m
        if errorlevel 1 (
          kubectl -n %NS% wait --for=condition=failed job/%JOB% --timeout=1s
        )

        echo ===== k6 pod(s) =====
        kubectl -n %NS% get pods -l app=k6 -o wide

        echo ===== k6 logs =====
     for /f "delims=" %%i in ('kubectl -n %NS% get pods -l app=k6 -o name') do (
  echo --- Logs for %%i ---
  kubectl -n %NS% logs --timestamps=true %%i
)

        echo ===== Decide pass/fail based on Job status =====
        for /f "delims=" %%F in ('kubectl -n %NS% get job/%JOB% -o jsonpath="{.status.failed}" 2^>nul') do set "FAILED=%%F"
        for /f "delims=" %%S in ('kubectl -n %NS% get job/%JOB% -o jsonpath="{.status.succeeded}" 2^>nul') do set "SUCCEEDED=%%S"

        if not "!FAILED!"=="" if not "!FAILED!"=="0" (
          echo k6 Job FAILED
          exit /b 1
        )

        if not "!SUCCEEDED!"=="" if not "!SUCCEEDED!"=="0" (
          echo k6 Job SUCCEEDED
          exit /b 0
        )

        echo k6 Job ended without succeeded/failed counts (treat as failure)
        exit /b 1
      '''
    }
  }
}

  }

  post {
    always {
      archiveArtifacts artifacts: 'k8s/**/*,loadtest/**/*,Dockerfile,Jenkinsfile,requirements.txt,README.md', fingerprint: true
    }
  }
}
