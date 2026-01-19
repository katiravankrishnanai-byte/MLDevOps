

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
    // Ensure files are present from Git
    checkout scm

    withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG_FILE')]) {
      bat '''
        @echo on
        setlocal EnableExtensions EnableDelayedExpansion

        rem ===== Config =====
        set "KUBECONFIG=%KUBECONFIG_FILE%"
        set "NS=%NAMESPACE%"
        set "JOB=k6"
        set "CM=k6-script"
        set "SCRIPT=loadtest\\k6.js"
        set "FAIL_BUILD=0"

        rem Provide a default namespace if not set
        if "%NS%"=="" set "NS=mldevopskatir"
        set BASE_URL=http://mldevops:8000

        rem ===== 1) Validation: Verify k6 script exists in workspace =====
        if not exist "%SCRIPT%" (
          echo ERROR: k6 script not found at path: %CD%\\%SCRIPT%
          dir /s loadtest
          exit /b 1
        )

        echo ===== k6: cleanup old resources =====
        kubectl -n %NS% delete job %JOB% --ignore-not-found
        kubectl -n %NS% delete configmap %CM% --ignore-not-found

        echo ===== k6: create configmap from script in workspace =====
        kubectl -n %NS% create configmap %CM% --from-file=k6.js="%SCRIPT%"
        if errorlevel 1 (
          set "FAIL_BUILD=1"
          goto k6_logs
        )

        echo ===== k6: generate job manifest =====
        (
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
          echo           value: "http://%SERVICE%:8000"
          echo         volumeMounts:
          echo         - name: script
          echo           mountPath: /scripts
          echo         command: ["k6","run","/scripts/k6.js"]
          echo       volumes:
          echo       - name: script
          echo         configMap:
          echo           name: %CM%
        ) > k6-job.yaml

        echo ===== k6: apply job =====
        kubectl apply -f k6-job.yaml
        if errorlevel 1 (
          set "FAIL_BUILD=1"
          goto k6_logs
        )

        echo ===== k6: wait for completion (watch) =====
        kubectl -n %NS% wait --for=condition=complete job/%JOB% --timeout=5m --request-timeout=60s
        if errorlevel 1 (
          echo ===== k6: watch wait failed; polling as fallback =====
          set /a MAX=30
          for /l %%X in (1,1,!MAX!) do (
            set "SUC="
            set "FAIL="
            for /f "delims=" %%S in ('kubectl -n %NS% get job/%JOB% -o jsonpath^="{.status.succeeded}" 2^>nul') do set "SUC=%%S"
            for /f "delims=" %%F in ('kubectl -n %NS% get job/%JOB% -o jsonpath^="{.status.failed}"    2^>nul') do set "FAIL=%%F"
            if not "!SUC!"=="" if not "!SUC!"=="0" goto k6_success
            if not "!FAIL!"=="" if not "!FAIL!"=="0" goto k6_failed
            echo still waiting... (%%X/!MAX!)
            timeout /t 10 >nul
          )
          echo ERROR: k6 job polling timeout
          goto k6_failed
        )

        :k6_success
        echo ===== k6: job reported success =====
        echo ===== k6: final logs =====
        for /f "delims=" %%i in ('kubectl -n %NS% get pods -l app^=k6 -o name') do (
          echo --- Logs for %%i ---
          kubectl -n %NS% logs --timestamps=true %%i
        )
        goto k6_end

        :k6_failed
        echo ===== k6: job reported failure =====
        set "FAIL_BUILD=1"

        :k6_logs
        echo ===== k6: pod summary =====
        kubectl -n %NS% get pods -l app^=k6 -o wide || echo ^(pod listing failed^)

        echo ===== k6: logs =====
        for /f "delims=" %%i in ('kubectl -n %NS% get pods -l app^=k6 -o name') do (
          echo --- Logs for %%i ---
          kubectl -n %NS% logs --timestamps=true %%i
        )

        echo ===== k6: describe job =====
        kubectl -n %NS% describe job/%JOB%

        :k6_end
        if "%FAIL_BUILD%"=="1" exit /b 1

        endlocal
      '''
    }
  }
  post {
    always {
      archiveArtifacts artifacts: 'k6-job.yaml', fingerprint: true
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
